"""Booth code deployment — the admin view's API and the SSH push it queues."""

import re
import subprocess
import tarfile
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.tolls import booth_deploy
from apps.tolls.models import (
    BoothDeployJob, BoothJobStatus, BoothMachine, Plaza, TollLane,
)
from apps.users.models import User, UserRole


def _completed(returncode=0, stdout='', stderr=''):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


class BoothDeploymentApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            phone='03001234567', password='testpass123', full_name='Admin',
            user_role=UserRole.ADMIN, is_staff=True,
        )
        self.client.force_authenticate(user=self.admin)
        self.plaza = Plaza.objects.create(plaza_id=2, name='Test Plaza')
        self.lane = TollLane.objects.create(plaza=self.plaza, lane_number=8)

    def test_lanes_without_a_machine_still_appear(self):
        """"Nowhere to deploy to" is the state an operator most needs to see."""
        res = self.client.get('/api/v1/tolls/admin/booth-deployments/')
        self.assertEqual(res.status_code, 200)
        data = res.json()['data']
        self.assertEqual(len(data['booths']), 1)
        row = data['booths'][0]
        self.assertIsNone(row['id'])
        self.assertEqual(row['lane_number'], 8)
        self.assertEqual(row['host'], '')

    def test_master_version_is_reported(self):
        res = self.client.get('/api/v1/tolls/admin/booth-deployments/')
        self.assertTrue(res.json()['data']['master_version'])

    def test_configure_and_list_machine(self):
        res = self.client.post('/api/v1/tolls/admin/booth-deployments/', {
            'lane': self.lane.id, 'host': '192.168.79.58', 'ssh_port': 22,
        }, format='json')
        self.assertEqual(res.status_code, 200)

        machine = BoothMachine.objects.get(lane=self.lane)
        self.assertEqual(machine.host, '192.168.79.58')

        row = self.client.get('/api/v1/tolls/admin/booth-deployments/').json()['data']['booths'][0]
        self.assertEqual(row['host'], '192.168.79.58')
        self.assertEqual(row['plaza_name'], 'Test Plaza')

    def test_configuring_the_same_lane_twice_updates_it(self):
        for host in ('192.168.79.58', '192.168.79.59'):
            res = self.client.post('/api/v1/tolls/admin/booth-deployments/', {
                'lane': self.lane.id, 'host': host,
            }, format='json')
            self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(BoothMachine.objects.filter(lane=self.lane).count(), 1)
        self.assertEqual(BoothMachine.objects.get(lane=self.lane).host, '192.168.79.59')

    def test_queue_update_job(self):
        machine = BoothMachine.objects.create(lane=self.lane, host='10.0.0.5')
        res = self.client.post(
            f'/api/v1/tolls/admin/booth-machines/{machine.id}/jobs/',
            {'action': 'update'}, format='json',
        )
        self.assertEqual(res.status_code, 201)
        job = BoothDeployJob.objects.get()
        self.assertEqual(job.status, BoothJobStatus.PENDING)
        self.assertEqual(job.requested_by, self.admin)
        # Queued only — the request must never touch the booth itself.
        self.assertIsNone(job.started_at)

    def test_second_job_while_one_is_in_flight_is_refused(self):
        """A double click must not deploy to the same booth twice."""
        machine = BoothMachine.objects.create(lane=self.lane, host='10.0.0.5')
        url = f'/api/v1/tolls/admin/booth-machines/{machine.id}/jobs/'
        self.assertEqual(self.client.post(url, {'action': 'update'}, format='json').status_code, 201)
        self.assertEqual(self.client.post(url, {'action': 'update'}, format='json').status_code, 409)
        self.assertEqual(BoothDeployJob.objects.count(), 1)

    def test_finished_job_does_not_block_a_new_one(self):
        machine = BoothMachine.objects.create(lane=self.lane, host='10.0.0.5')
        BoothDeployJob.objects.create(
            machine=machine, action='update', status=BoothJobStatus.SUCCEEDED,
        )
        res = self.client.post(
            f'/api/v1/tolls/admin/booth-machines/{machine.id}/jobs/',
            {'action': 'update'}, format='json',
        )
        self.assertEqual(res.status_code, 201)

    def test_invalid_action_is_rejected(self):
        machine = BoothMachine.objects.create(lane=self.lane, host='10.0.0.5')
        res = self.client.post(
            f'/api/v1/tolls/admin/booth-machines/{machine.id}/jobs/',
            {'action': 'rm -rf'}, format='json',
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(BoothDeployJob.objects.count(), 0)

    def test_non_admin_cannot_reach_any_of_it(self):
        machine = BoothMachine.objects.create(lane=self.lane, host='10.0.0.5')
        operator = User.objects.create_user(
            phone='03009999999', password='testpass123', full_name='Op',
            user_role=UserRole.OPERATOR,
        )
        self.client.force_authenticate(user=operator)
        self.assertEqual(
            self.client.get('/api/v1/tolls/admin/booth-deployments/').status_code, 403)
        self.assertEqual(
            self.client.post(f'/api/v1/tolls/admin/booth-machines/{machine.id}/jobs/',
                             {'action': 'update'}, format='json').status_code, 403)


class BoothCheckTests(TestCase):
    def setUp(self):
        plaza = Plaza.objects.create(plaza_id=2, name='P')
        lane = TollLane.objects.create(plaza=plaza, lane_number=1)
        self.machine = BoothMachine.objects.create(lane=lane, host='10.0.0.5')

    def test_parses_version_and_pm2_state(self):
        stdout = (
            "1.2.3\n---PM2---\n"
            '[{"name":"mtag-web","pm2_env":{"status":"online"}},'
            '{"name":"mtag-gate","pm2_env":{"status":"stopped"}}]'
        )
        with patch.object(booth_deploy, 'ssh', return_value=_completed(0, stdout)):
            result = booth_deploy.check(self.machine)
        self.assertTrue(result['reachable'])
        self.assertEqual(result['version'], '1.2.3')
        self.assertEqual(result['pm2'], 'mtag-web: online, mtag-gate: stopped')

    def test_booth_without_a_version_file_reads_as_unknown(self):
        """Booths deployed before this feature have no VERSION — not an error."""
        with patch.object(booth_deploy, 'ssh', return_value=_completed(0, "\n---PM2---\n[]")):
            result = booth_deploy.check(self.machine)
        self.assertTrue(result['reachable'])
        self.assertEqual(result['version'], 'unknown')

    def test_unreachable_booth(self):
        with patch.object(booth_deploy, 'ssh',
                          return_value=_completed(255, '', 'ssh: connect to host ... refused')):
            result = booth_deploy.check(self.machine)
        self.assertFalse(result['reachable'])
        self.assertIn('refused', result['log'])

    def test_non_json_pm2_output_is_kept_verbatim(self):
        stdout = "1.0.0\n---PM2---\npm2: command not found"
        with patch.object(booth_deploy, 'ssh', return_value=_completed(0, stdout)):
            result = booth_deploy.check(self.machine)
        self.assertIn('command not found', result['pm2'])


class BundleTests(TestCase):
    """The archive master ships to a booth."""

    def test_bundle_excludes_secrets_and_wheelhouse_but_keeps_version(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tarball = booth_deploy.build_bundle(Path(tmp))
            names = tarfile.open(tarball).getnames()

        self.assertTrue(any(n.endswith('/VERSION') for n in names), "VERSION must ship")
        self.assertTrue(any(n.endswith('/manage.py') for n in names))
        # Master has no wheelhouse; shipping one would be 34MB of nothing.
        self.assertFalse(any('/wheelhouse/' in n for n in names))
        self.assertFalse(any(n.endswith('/venv') or '/venv/' in n for n in names))
        for secret in ('/.env', '/.env.master', '/.env.booth'):
            self.assertFalse(
                any(n.rstrip('/').endswith(secret) for n in names),
                f"{secret} must never be shipped",
            )
        # The template booth_update.sh needs when a booth has no .env yet.
        self.assertTrue(any(n.endswith('/.env.booth.example') for n in names))


class UpdatePreservationTests(TestCase):
    """The purge step is the one that can brick a lane — assert it precisely."""

    def setUp(self):
        plaza = Plaza.objects.create(plaza_id=2, name='P')
        lane = TollLane.objects.create(plaza=plaza, lane_number=1)
        self.machine = BoothMachine.objects.create(lane=lane, host='10.0.0.5')

    def _capture_scripts(self):
        scripts = []

        def fake_ssh(machine, script, timeout):
            scripts.append(script)
            return _completed(0, 'ok')

        return scripts, fake_ssh

    def test_purge_keeps_the_booths_wheelhouse_and_config(self):
        """Master ships no wheelhouse, so deleting the booth's would strand pip.

        booth_update.sh installs with --no-index from wheelhouse/; a booth has no
        route to PyPI, so a purge that removed it would exit 5 with the lane down.
        """
        scripts, fake_ssh = self._capture_scripts()
        with patch.object(booth_deploy, 'ssh', fake_ssh), \
             patch.object(booth_deploy, 'scp', return_value=_completed(0)):
            result = booth_deploy.update(self.machine, timeout=60)

        self.assertTrue(result['ok'])
        purge = next(s for s in scripts if 'find ' in s)
        for keep in ('wheelhouse', 'venv', '.env', 'rfid_config.ini',
                     'offline_cache.db', 'staticfiles'):
            self.assertRegex(purge, rf"! -name '?{re.escape(keep)}'?",
                             f"{keep} must survive a code push")

    def test_update_runs_booth_update_which_restarts_pm2(self):
        scripts, fake_ssh = self._capture_scripts()
        with patch.object(booth_deploy, 'ssh', fake_ssh), \
             patch.object(booth_deploy, 'scp', return_value=_completed(0)):
            booth_deploy.update(self.machine, timeout=60)
        self.assertTrue(any('booth_update.sh' in s for s in scripts))

    def test_failed_copy_stops_before_anything_is_deleted(self):
        """No window where the booth has neither the old code nor the new."""
        scripts, fake_ssh = self._capture_scripts()
        with patch.object(booth_deploy, 'ssh', fake_ssh), \
             patch.object(booth_deploy, 'scp',
                          return_value=_completed(1, '', 'No route to host')):
            result = booth_deploy.update(self.machine, timeout=60)

        self.assertFalse(result['ok'])
        self.assertEqual(scripts, [], "nothing may run on the booth after a failed copy")

    def test_booth_update_exit_code_is_explained(self):
        def fake_ssh(machine, script, timeout):
            return _completed(0) if 'find ' in script else _completed(7, '', 'db unreachable')

        with patch.object(booth_deploy, 'ssh', fake_ssh), \
             patch.object(booth_deploy, 'scp', return_value=_completed(0)):
            result = booth_deploy.update(self.machine, timeout=60)

        self.assertFalse(result['ok'])
        self.assertEqual(result['exit_code'], 7)
        self.assertIn("cannot reach master's database", result['log'])


class WorkerTests(TestCase):
    def setUp(self):
        plaza = Plaza.objects.create(plaza_id=2, name='P')
        lane = TollLane.objects.create(plaza=plaza, lane_number=1)
        self.machine = BoothMachine.objects.create(lane=lane, host='10.0.0.5')

    def _run_worker(self):
        from django.core.management import call_command
        call_command('booth_deploy_worker', '--once')

    def test_check_job_records_the_booths_version(self):
        job = BoothDeployJob.objects.create(machine=self.machine, action='check')
        stdout = '1.2.3\n---PM2---\n[{"name":"mtag-web","pm2_env":{"status":"online"}}]'
        with patch.object(booth_deploy, 'ssh', return_value=_completed(0, stdout)):
            self._run_worker()

        job.refresh_from_db()
        self.machine.refresh_from_db()
        self.assertEqual(job.status, BoothJobStatus.SUCCEEDED)
        self.assertEqual(self.machine.reported_version, '1.2.3')
        self.assertTrue(self.machine.reachable)
        self.assertIsNotNone(job.finished_at)

    def test_unreachable_booth_fails_the_job_and_is_recorded(self):
        job = BoothDeployJob.objects.create(machine=self.machine, action='check')
        with patch.object(booth_deploy, 'ssh', return_value=_completed(255, '', 'timed out')):
            self._run_worker()

        job.refresh_from_db()
        self.machine.refresh_from_db()
        self.assertEqual(job.status, BoothJobStatus.FAILED)
        self.assertFalse(self.machine.reachable)
        self.assertIn('timed out', self.machine.last_error)

    def test_update_on_an_unreachable_booth_changes_nothing(self):
        job = BoothDeployJob.objects.create(machine=self.machine, action='update')
        with patch.object(booth_deploy, 'ssh', return_value=_completed(255, '', 'no route')), \
             patch.object(booth_deploy, 'scp') as scp:
            self._run_worker()

        job.refresh_from_db()
        self.assertEqual(job.status, BoothJobStatus.FAILED)
        scp.assert_not_called()
        self.machine.refresh_from_db()
        self.assertIsNone(self.machine.last_deployed_at)

    def test_successful_update_stamps_the_new_version(self):
        job = BoothDeployJob.objects.create(machine=self.machine, action='update')
        calls = {'n': 0}

        def fake_ssh(machine, script, timeout):
            # The worker checks before and after; report the old version first
            # and the new one once the push has run.
            if '---PM2---' in script or 'VERSION' in script:
                calls['n'] += 1
                version = '1.0.0' if calls['n'] == 1 else '9.9.9'
                return _completed(0, f'{version}\n---PM2---\n[]')
            return _completed(0, 'ok')

        with patch.object(booth_deploy, 'ssh', fake_ssh), \
             patch.object(booth_deploy, 'scp', return_value=_completed(0)):
            self._run_worker()

        job.refresh_from_db()
        self.machine.refresh_from_db()
        self.assertEqual(job.status, BoothJobStatus.SUCCEEDED)
        self.assertEqual(job.from_version, '1.0.0')
        self.assertEqual(self.machine.reported_version, '9.9.9')
        self.assertIsNotNone(self.machine.last_deployed_at)

    def test_worker_leaves_no_job_stuck_running_when_a_step_crashes(self):
        job = BoothDeployJob.objects.create(machine=self.machine, action='check')
        with patch.object(booth_deploy, 'ssh', side_effect=RuntimeError('boom')):
            self._run_worker()

        job.refresh_from_db()
        self.assertEqual(job.status, BoothJobStatus.FAILED)
        self.assertIn('boom', job.log)

    def test_worker_ignores_jobs_that_already_finished(self):
        job = BoothDeployJob.objects.create(
            machine=self.machine, action='check', status=BoothJobStatus.SUCCEEDED,
        )
        with patch.object(booth_deploy, 'ssh') as ssh:
            self._run_worker()
        ssh.assert_not_called()
        job.refresh_from_db()
        self.assertEqual(job.status, BoothJobStatus.SUCCEEDED)


@override_settings(BOOTH_SSH_PASSWORD='secret', BOOTH_SSH_USER='iteck')
class SshInvocationTests(TestCase):
    def setUp(self):
        plaza = Plaza.objects.create(plaza_id=2, name='P')
        lane = TollLane.objects.create(plaza=plaza, lane_number=1)
        self.machine = BoothMachine.objects.create(lane=lane, host='10.0.0.5', ssh_port=1122)

    def test_password_never_appears_in_argv(self):
        """sshpass -e reads SSHPASS from the environment; argv is world-readable."""
        with patch.object(booth_deploy, '_run', return_value=_completed(0)) as run:
            booth_deploy.ssh(self.machine, 'true', 30)
        argv, _timeout = run.call_args[0]
        self.assertNotIn('secret', ' '.join(argv))
        self.assertEqual(argv[:2], ['sshpass', '-e'])
        self.assertEqual(booth_deploy._env()['SSHPASS'], 'secret')

    def test_stdin_is_closed_so_remote_sudo_cannot_hang(self):
        with patch.object(booth_deploy, '_run', return_value=_completed(0)) as run:
            booth_deploy.ssh(self.machine, 'true', 30)
        argv, _timeout = run.call_args[0]
        self.assertIn('-n', argv)

    def test_per_machine_user_and_port_win(self):
        self.machine.ssh_user = 'mew02'
        with patch.object(booth_deploy, '_run', return_value=_completed(0)) as run:
            booth_deploy.ssh(self.machine, 'true', 30)
        argv, _timeout = run.call_args[0]
        self.assertIn('mew02@10.0.0.5', argv)
        self.assertIn('1122', argv)

    @override_settings(BOOTH_SSH_PASSWORD='')
    def test_key_auth_does_not_shell_out_to_sshpass(self):
        with patch.object(booth_deploy, '_run', return_value=_completed(0)) as run:
            booth_deploy.ssh(self.machine, 'true', 30)
        argv, _timeout = run.call_args[0]
        self.assertEqual(argv[0], 'ssh')

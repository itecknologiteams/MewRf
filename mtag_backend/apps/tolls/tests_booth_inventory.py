"""The lane→address map master owns: list_booths and discover_booths."""

import subprocess
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.tolls import booth_deploy
from apps.tolls.models import BoothMachine, Plaza, TollLane


def _completed(returncode=0, stdout='', stderr=''):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


CONFIG = """
[gate]
mode = entry
plaza_id = {plaza}
lane_number = {lane}

[scanner]
reader_host = 192.168.78.14
"""


class ListBoothsTests(TestCase):
    def setUp(self):
        self.plaza = Plaza.objects.create(plaza_id=2, name='Test Plaza')
        self.lane1 = TollLane.objects.create(plaza=self.plaza, lane_number=1)
        self.lane2 = TollLane.objects.create(plaza=self.plaza, lane_number=2)

    def _run(self, *args):
        out, err = StringIO(), StringIO()
        call_command('list_booths', *args, stdout=out, stderr=err)
        return out.getvalue(), err.getvalue()

    def test_stdout_is_only_hosts(self):
        """deploy_booths.sh reads stdout directly — nothing else may land there."""
        BoothMachine.objects.create(lane=self.lane1, host='192.168.78.2')
        BoothMachine.objects.create(lane=self.lane2, host='192.168.78.7')
        out, _ = self._run()
        self.assertEqual(out.split(), ['192.168.78.2', '192.168.78.7'])

    def test_hosts_are_ordered_by_plaza_then_lane(self):
        other = Plaza.objects.create(plaza_id=1, name='First')
        lane = TollLane.objects.create(plaza=other, lane_number=9)
        BoothMachine.objects.create(lane=self.lane2, host='10.0.0.2')
        BoothMachine.objects.create(lane=self.lane1, host='10.0.0.1')
        BoothMachine.objects.create(lane=lane, host='10.0.0.9')
        out, _ = self._run()
        self.assertEqual(out.split(), ['10.0.0.9', '10.0.0.1', '10.0.0.2'])

    def test_lanes_without_an_address_are_named_on_stderr(self):
        """The one hazard of a database-sourced list: a booth nobody recorded."""
        BoothMachine.objects.create(lane=self.lane1, host='192.168.78.2')
        out, err = self._run()
        self.assertEqual(out.split(), ['192.168.78.2'])
        self.assertIn('1 lane(s) have no booth address', err)
        self.assertIn('Test Plaza lane 2', err)
        self.assertIn('discover_booths', err)

    def test_no_warning_when_every_lane_is_covered(self):
        BoothMachine.objects.create(lane=self.lane1, host='10.0.0.1')
        BoothMachine.objects.create(lane=self.lane2, host='10.0.0.2')
        _, err = self._run()
        self.assertNotIn('WARNING', err)

    def test_machine_with_a_blank_host_counts_as_missing(self):
        BoothMachine.objects.create(lane=self.lane1, host='')
        out, err = self._run()
        self.assertEqual(out.strip(), '')
        self.assertIn('Test Plaza lane 1', err)

    def test_active_only_skips_deactivated_lanes(self):
        self.lane2.is_active = False
        self.lane2.save()
        BoothMachine.objects.create(lane=self.lane1, host='10.0.0.1')
        BoothMachine.objects.create(lane=self.lane2, host='10.0.0.2')
        out, err = self._run('--active-only')
        self.assertEqual(out.split(), ['10.0.0.1'])
        self.assertNotIn('WARNING', err)

    def test_deactivated_lanes_are_included_by_default_but_flagged(self):
        self.lane2.is_active = False
        self.lane2.save()
        BoothMachine.objects.create(lane=self.lane1, host='10.0.0.1')
        BoothMachine.objects.create(lane=self.lane2, host='10.0.0.2')
        out, err = self._run()
        self.assertEqual(out.split(), ['10.0.0.1', '10.0.0.2'])
        self.assertIn('deactivated lanes', err)

    def test_table_mode_is_readable_not_parseable(self):
        BoothMachine.objects.create(lane=self.lane1, host='10.0.0.1', reported_version='1.0.0')
        out, _ = self._run('--table')
        self.assertIn('PLAZA', out)
        self.assertIn('Test Plaza', out)
        self.assertIn('1.0.0', out)


class DiscoverBoothsTests(TestCase):
    def setUp(self):
        self.plaza = Plaza.objects.create(plaza_id=2, name='Test Plaza')
        self.lane = TollLane.objects.create(plaza=self.plaza, lane_number=8)

    def _run(self, *args, ssh=None, **kwargs):
        out, err = StringIO(), StringIO()
        with patch.object(booth_deploy, 'ssh', ssh or (lambda *a, **k: _completed(0))):
            call_command('discover_booths', *args, stdout=out, stderr=err, **kwargs)
        return out.getvalue()

    def _config_ssh(self, plaza=2, lane=8):
        return lambda *a, **k: _completed(0, CONFIG.format(plaza=plaza, lane=lane))

    def test_records_the_lane_a_booth_reports(self):
        out = self._run('192.168.79.58', ssh=self._config_ssh())
        machine = BoothMachine.objects.get()
        self.assertEqual(machine.host, '192.168.79.58')
        self.assertEqual(machine.lane, self.lane)
        self.assertIn('recorded 1', out)

    def test_rerunning_moves_a_booth_to_its_new_address(self):
        """A re-addressed booth is re-recorded, and the move is announced."""
        BoothMachine.objects.create(lane=self.lane, host='192.168.79.58')
        out = self._run('192.168.79.99', ssh=self._config_ssh())
        self.assertEqual(BoothMachine.objects.count(), 1)
        self.assertEqual(BoothMachine.objects.get().host, '192.168.79.99')
        self.assertIn('was 192.168.79.58', out)

    def test_unreachable_booth_is_skipped_not_recorded(self):
        out = self._run(
            '10.0.0.5',
            ssh=lambda *a, **k: _completed(255, '', 'ssh: connect to host: refused'),
        )
        self.assertEqual(BoothMachine.objects.count(), 0)
        self.assertIn('unreachable', out)
        self.assertIn('skipped 1', out)

    def test_unprovisioned_booth_is_skipped(self):
        out = self._run('10.0.0.5', ssh=lambda *a, **k: _completed(0, ''))
        self.assertEqual(BoothMachine.objects.count(), 0)
        self.assertIn('no rfid_config.ini', out)

    def test_unknown_plaza_is_skipped(self):
        out = self._run('10.0.0.5', ssh=self._config_ssh(plaza=99))
        self.assertEqual(BoothMachine.objects.count(), 0)
        self.assertIn('unknown plaza', out)

    def test_unknown_lane_is_skipped_unless_asked_to_create_it(self):
        out = self._run('10.0.0.5', ssh=self._config_ssh(lane=42))
        self.assertEqual(BoothMachine.objects.count(), 0)
        self.assertIn('unknown lane', out)

        self._run('10.0.0.5', '--create-lanes', ssh=self._config_ssh(lane=42))
        self.assertTrue(TollLane.objects.filter(plaza=self.plaza, lane_number=42).exists())
        self.assertEqual(BoothMachine.objects.get().host, '10.0.0.5')

    def test_two_booths_claiming_one_lane_is_refused(self):
        """One of them is misconfigured; recording the second would hide that."""
        out = self._run('10.0.0.5', '10.0.0.6', ssh=self._config_ssh())
        self.assertEqual(BoothMachine.objects.count(), 1)
        self.assertEqual(BoothMachine.objects.get().host, '10.0.0.5')
        self.assertIn('lane conflict', out)

    def test_a_uuid_plaza_id_is_reported_not_crashed_on(self):
        ssh = lambda *a, **k: _completed(  # noqa: E731
            0, CONFIG.format(plaza='3f2b8c1e-0000-4000-8000-000000000000', lane=8),
        )
        out = self._run('10.0.0.5', ssh=ssh)
        self.assertEqual(BoothMachine.objects.count(), 0)
        self.assertIn('must be integers', out)

    def test_blank_lane_number_is_reported(self):
        out = self._run('10.0.0.5', ssh=self._config_ssh(lane=''))
        self.assertEqual(BoothMachine.objects.count(), 0)
        self.assertIn('lane_number is blank', out)

    def test_dry_run_writes_nothing(self):
        out = self._run('192.168.79.58', '--dry-run', ssh=self._config_ssh())
        self.assertEqual(BoothMachine.objects.count(), 0)
        self.assertIn('DRY RUN', out)
        self.assertIn('recorded 1', out)

    def test_duplicate_input_addresses_do_not_self_conflict(self):
        out = self._run('10.0.0.5', '10.0.0.5', ssh=self._config_ssh())
        self.assertNotIn('conflict', out)
        self.assertIn('recorded 1', out)

    def test_from_file_ignores_comments_quotes_and_blanks(self):
        import tempfile
        with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False) as handle:
            handle.write('# booths\n"10.0.0.5"\n\n  # skip\n')
            path = handle.name
        out = self._run('--from-file', path, ssh=self._config_ssh())
        self.assertEqual(BoothMachine.objects.get().host, '10.0.0.5')
        self.assertIn('recorded 1', out)

    def test_no_hosts_is_an_error_rather_than_a_silent_no_op(self):
        with self.assertRaises(CommandError):
            self._run()

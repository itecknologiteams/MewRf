"""Runs on MASTER. Executes the booth check/update jobs the portal queues.

Why a worker and not the request: pushing code to a booth means an scp, a purge,
a dependency install and a PM2 restart — minutes on a slow booth. A gunicorn
worker held that long is one fewer worker serving 21 lanes, and the operator's
browser would time out long before the deploy finished.

Add to master's PM2 alongside mtag-master:
    pm2 start ecosystem.master.config.js --only mtag-deploy
"""

import time
import traceback

from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction, close_old_connections
from django.utils import timezone

from apps.tolls.models import BoothDeployJob, BoothJobAction, BoothJobStatus
from apps.tolls import booth_deploy
from utils.code_version import get_code_version

POLL_SECONDS = 3


class Command(BaseCommand):
    help = "Execute queued booth code check/update jobs (master only)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--once', action='store_true',
            help="Drain the queue and exit, instead of polling forever.",
        )
        parser.add_argument(
            '--poll', type=float, default=POLL_SECONDS,
            help=f"Seconds between polls (default {POLL_SECONDS}).",
        )

    def handle(self, *args, **options):
        self.stdout.write(f"booth deploy worker — master version {get_code_version()}")
        if not booth_deploy.sshpass_available():
            # Not fatal: jobs still run and fail with a clear log. Saying it once
            # at startup is what turns 21 identical failures into one fix.
            self.stdout.write(self.style.WARNING(
                "!!! BOOTH_SSH_PASSWORD is set but sshpass is not installed — "
                "every job will fail. sudo apt-get install -y sshpass"
            ))

        while True:
            worked = False
            while self._run_next():
                worked = True
            if options['once']:
                if not worked:
                    self.stdout.write("queue empty")
                return
            time.sleep(options['poll'])

    # ── Job loop ─────────────────────────────────────────────────────────────

    def _claim(self):
        """Take the oldest pending job, atomically.

        skip_locked so a second worker (or an accidental duplicate PM2 app)
        picks a different row instead of blocking on this one — two workers
        deploying to the same booth at once would fight over its code tree.
        """
        with transaction.atomic():
            job = (
                BoothDeployJob.objects
                .select_for_update(skip_locked=True)
                .filter(status=BoothJobStatus.PENDING)
                .order_by('requested_at')
                .first()
            )
            if job is None:
                return None
            job.status = BoothJobStatus.RUNNING
            job.started_at = timezone.now()
            job.save(update_fields=['status', 'started_at'])
        return job

    def _run_next(self) -> bool:
        # A long deploy can outlive Postgres' idle timeout; drop dead handles
        # before touching the database again.
        close_old_connections()
        job = self._claim()
        if job is None:
            return False

        machine = job.machine
        self.stdout.write(f"[{job.id}] {job.action} → {machine.host} (lane {machine.lane.lane_number})")
        try:
            if job.action == BoothJobAction.CHECK:
                self._do_check(job, machine)
            else:
                self._do_update(job, machine)
        except Exception:
            # A crash here must not leave the row RUNNING forever — the portal
            # would show a spinner that never resolves.
            self._finish(job, BoothJobStatus.FAILED, job.log + '\n' + traceback.format_exc(), None)
            self.stdout.write(self.style.ERROR(f"[{job.id}] crashed"))
        return True

    # ── Actions ──────────────────────────────────────────────────────────────

    def _do_check(self, job, machine):
        result = booth_deploy.check(machine)
        self._record(machine, result)
        job.from_version = result['version']
        job.to_version = get_code_version()
        status = BoothJobStatus.SUCCEEDED if result['reachable'] else BoothJobStatus.FAILED
        self._finish(job, status, result['log'], 0 if result['reachable'] else 1)
        self.stdout.write(f"[{job.id}] {'ok' if result['reachable'] else 'unreachable'} — {result['version']}")

    def _do_update(self, job, machine):
        before = booth_deploy.check(machine)
        self._record(machine, before)
        job.from_version = before['version']
        job.to_version = get_code_version()
        job.save(update_fields=['from_version', 'to_version'])

        if not before['reachable']:
            self._finish(
                job, BoothJobStatus.FAILED,
                before['log'] + "\n!!! Booth is unreachable — nothing was changed.", 1,
            )
            return

        timeout = getattr(settings, 'BOOTH_DEPLOY_TIMEOUT', 1800)
        result = booth_deploy.update(machine, timeout)

        # Re-read the booth either way: a failure partway through still leaves it
        # in *some* state, and the portal must show that rather than the version
        # it had before the attempt.
        after = booth_deploy.check(machine)
        self._record(machine, after)
        if result['ok']:
            machine.last_deployed_at = timezone.now()
            machine.save(update_fields=['last_deployed_at'])

        log = f"{result['log']}\n\n--- booth state after the update ---\n{after['log']}"
        status = BoothJobStatus.SUCCEEDED if result['ok'] else BoothJobStatus.FAILED
        self._finish(job, status, log, result['exit_code'])
        self.stdout.write(
            f"[{job.id}] {'updated' if result['ok'] else 'FAILED'} — "
            f"{job.from_version} → {after['version']}"
        )

    # ── Persistence ──────────────────────────────────────────────────────────

    def _record(self, machine, result):
        machine.reachable = result['reachable']
        machine.last_checked_at = timezone.now()
        if result['reachable']:
            machine.reported_version = result['version']
            machine.pm2_summary = result['pm2']
            machine.last_error = ''
        else:
            machine.last_error = result['log'][-2000:]
        machine.save(update_fields=[
            'reachable', 'last_checked_at', 'reported_version',
            'pm2_summary', 'last_error', 'updated_at',
        ])

    def _finish(self, job, status, log, exit_code):
        job.status = status
        job.log = (log or '')[-60000:]
        job.exit_code = exit_code
        job.finished_at = timezone.now()
        job.save()

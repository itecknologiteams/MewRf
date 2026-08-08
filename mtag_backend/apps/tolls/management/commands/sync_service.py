"""
The sync service — the ONLY process that talks to master.

    python manage.py sync_service              # loop forever at SYNC_INTERVAL
    python manage.py sync_service --once       # one cycle, then exit
    python manage.py sync_service --mode exit  # override GATE_MODE from .env

Runs as PM2 app `mtag-sync`. Deliberately separate from `mtag-web` and
`mtag-gate`: the gate reads and writes only its local database and carries no
replication logic, so master being down delays reporting instead of closing a
lane.

Mode (GATE_MODE in .env):
    entry  push + pull(reference, closed trips)
    exit   push + pull(reference, closed trips, open trips)
"""
from django.core.management.base import BaseCommand, CommandError

from apps.tolls.sync.agent import (
    SYNC_INTERVAL, VALID_MODES, get_mode, run_cycle, _loop,
)


class Command(BaseCommand):
    help = "Run the booth<->master sync service (pull + push), driven by GATE_MODE."

    def add_arguments(self, parser):
        parser.add_argument(
            '--once', action='store_true', default=False,
            help='Run a single cycle and exit (useful for cron or verification).',
        )
        parser.add_argument(
            '--mode', default=None, choices=list(VALID_MODES),
            help='Override GATE_MODE from .env for this run.',
        )

    def handle(self, *args, **options):
        mode = options['mode'] or get_mode()
        if mode not in VALID_MODES:
            raise CommandError(f"mode must be one of {VALID_MODES}, got {mode!r}")

        pulls = ('reference + closed trips'
                 if mode == 'entry' else
                 'reference + closed trips + OPEN trips')
        self.stdout.write(self.style.SUCCESS(
            f"[sync] mode={mode} | pull: {pulls} | push: all local changes"
        ))

        if options['once']:
            result = run_cycle(mode)
            pull, push = result['pull'], result['push']
            self.stdout.write(f"  pull: {pull}")
            self.stdout.write(f"  push: {push}")
            if pull.get('error') or push.get('error'):
                raise CommandError("cycle completed with errors (see above)")
            failed = [k for k, v in push.items() if isinstance(v, str) and v.startswith('failed')]
            if failed:
                raise CommandError(
                    f"push held the watermark for: {', '.join(failed)} — "
                    "these rows are NOT on master and will be retried"
                )
            self.stdout.write(self.style.SUCCESS("  cycle OK"))
            return

        self.stdout.write(f"[sync] looping every {SYNC_INTERVAL}s — Ctrl-C to stop")
        try:
            _loop()
        except KeyboardInterrupt:
            self.stdout.write("\n[sync] stopped")

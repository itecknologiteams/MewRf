"""
DEPRECATED — use `manage.py sync_service` instead.

Kept as a thin shim so existing PM2 entries, cron jobs and runbooks keep working.
It delegates to sync_service rather than reimplementing the loop, because this
command was mode-unaware: it always ran the full pull, so an ENTRY booth would
copy in every other plaza's open trips it has no use for.

    python manage.py sync_service                # loop, mode from GATE_MODE
    python manage.py sync_service --once
    python manage.py sync_service --mode entry
"""
from django.core.management.base import BaseCommand

from apps.tolls.sync import agent


class Command(BaseCommand):
    help = "DEPRECATED — use 'sync_service'. Runs the booth<->master sync agent."

    def add_arguments(self, parser):
        parser.add_argument('--interval', type=int, default=None,
                            help='Sync interval in seconds (default: 30)')
        parser.add_argument('--once', action='store_true',
                            help='Run one cycle and exit (for testing)')
        parser.add_argument('--mode', default=None, choices=list(agent.VALID_MODES),
                            help='Override GATE_MODE from .env for this run.')

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING(
            "[sync] 'run_sync_agent' is deprecated — use 'manage.py sync_service'. "
            "Delegating."
        ))
        if options['interval']:
            # _loop() reads this module-level constant each iteration.
            agent.SYNC_INTERVAL = options['interval']

        from django.core.management import call_command
        call_command(
            'sync_service',
            **{k: v for k, v in (('once', options['once']), ('mode', options['mode']))
               if v},
        )

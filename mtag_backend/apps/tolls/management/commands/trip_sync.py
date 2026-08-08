"""
Inspect or run the Entry → Master → Exit trip sync pipeline.

    python manage.py trip_sync            # status only, changes nothing
    python manage.py trip_sync --once     # run one sync cycle, then show status

Use this during a booth deployment to prove the pipeline is live before opening
the lane. The DRIFT line is the one that matters: it counts trips this booth
still believes are open that master has already closed. Those are exactly the
rows that block a vehicle's next entry and let another lane try to charge an
already-paid trip, so it must read 0.
"""
from django.core.management.base import BaseCommand

from apps.tolls.sync.connections import (
    get_local_conn, get_master_conn, master_is_reachable,
)
from apps.tolls.sync.trip_sync import get_watermark, sync_trip_lifecycle


class Command(BaseCommand):
    help = "Inspect or run the Entry -> Master -> Exit trip sync pipeline."

    def add_arguments(self, parser):
        parser.add_argument(
            '--once',
            action='store_true',
            default=False,
            help='Run one sync cycle before reporting status.',
        )

    def handle(self, *args, **options):
        ok, warn, err = self.style.SUCCESS, self.style.WARNING, self.style.ERROR

        self.stdout.write("=== Trip sync: Entry -> Master -> Exit ===")

        if not master_is_reachable():
            self.stdout.write(err(
                "Master UNREACHABLE — entry and exit are both refused while this is "
                "true (online-only). Fix connectivity before opening the lane."
            ))
            return

        self.stdout.write(ok("Master reachable"))

        master_conn = get_master_conn()
        local_conn = get_local_conn()
        try:
            if options['once']:
                with master_conn, local_conn:
                    with master_conn.cursor() as mc, local_conn.cursor() as lc:
                        result = sync_trip_lifecycle(mc, lc)
                self.stdout.write(ok(
                    f"Sync cycle done — open={result['active']} closed={result['closed']}"
                ))

            with master_conn.cursor() as mc, local_conn.cursor() as lc:
                mc.execute("SELECT COUNT(*) FROM toll_trips WHERE status = 'active'")
                master_open = mc.fetchone()[0]

                lc.execute("SELECT COUNT(*) FROM toll_trips WHERE status = 'active'")
                local_open = lc.fetchone()[0]

                # Trips this booth thinks are open. Ask master what it really
                # thinks of those same ids — anything master does not still list
                # as active is stale here.
                lc.execute("SELECT id FROM toll_trips WHERE status = 'active'")
                local_ids = [str(r[0]) for r in lc.fetchall()]

                drift = []
                if local_ids:
                    mc.execute(
                        "SELECT id FROM toll_trips "
                        "WHERE id = ANY(%s) AND status = 'active'",
                        [local_ids],
                    )
                    still_open = {str(r[0]) for r in mc.fetchall()}
                    drift = [t for t in local_ids if t not in still_open]

                watermark = get_watermark(lc)

            self.stdout.write(f"  open trips on master : {master_open}")
            self.stdout.write(f"  open trips locally   : {local_open}")
            self.stdout.write(f"  closed-trip watermark: {watermark.isoformat()}")

            if drift:
                self.stdout.write(err(
                    f"  DRIFT                : {len(drift)} stale open trip(s) here"
                ))
                for tid in drift[:10]:
                    self.stdout.write(err(f"      {tid}"))
                if len(drift) > 10:
                    self.stdout.write(err(f"      ... and {len(drift) - 10} more"))
                self.stdout.write(warn(
                    "  Run with --once to clear them. If they persist, the "
                    "closed-trip pass is not reaching this booth."
                ))
            else:
                self.stdout.write(ok("  DRIFT                : 0 — booth agrees with master"))

            if master_open and not local_open:
                self.stdout.write(warn(
                    "  Master has open trips but this booth has none — if this booth "
                    "is an exit lane, run --once; vehicles would be turned away."
                ))
        finally:
            master_conn.close()
            local_conn.close()

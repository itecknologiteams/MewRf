"""Runs on MASTER. Prints the booth host list that deploy_booths.sh deploys to.

master is the single source of truth for which machine runs which lane, so the
deploy script asks here instead of carrying its own copy of the addresses. Two
copies drift: re-address a booth and the script would still reach it while the
portal reported it unreachable, or the reverse.

stdout is ONLY hosts, one per line, because a shell reads it directly. Anything
an operator needs to see — lanes with no machine recorded, inactive lanes — goes
to stderr so it cannot end up being treated as an address.
"""

from django.core.management.base import BaseCommand

from apps.tolls.models import BoothMachine, TollLane


class Command(BaseCommand):
    help = "Print every configured booth host, one per line (deploy_booths.sh reads this)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--table', action='store_true',
            help="Human-readable plaza/lane/host table instead of bare hosts.",
        )
        parser.add_argument(
            '--active-only', action='store_true',
            help="Skip booths whose lane is deactivated.",
        )

    def handle(self, *args, **options):
        machines = (
            BoothMachine.objects
            .select_related('lane', 'lane__plaza')
            .exclude(host='')
            .order_by('lane__plaza__plaza_id', 'lane__lane_number')
        )
        if options['active_only']:
            machines = machines.filter(lane__is_active=True)
        machines = list(machines)

        if options['table']:
            self._table(machines)
        else:
            for machine in machines:
                self.stdout.write(machine.host)

        self._warn_about_gaps(machines, options['active_only'])

    def _table(self, machines):
        if not machines:
            self.stdout.write("No booth machines recorded.")
            return
        self.stdout.write(f"{'PLAZA':<24} {'LANE':>5}  {'HOST':<16} {'VERSION':<10} LAST CHECKED")
        for m in machines:
            checked = m.last_checked_at.strftime('%Y-%m-%d %H:%M') if m.last_checked_at else 'never'
            self.stdout.write(
                f"{m.lane.plaza.name[:24]:<24} {m.lane.lane_number:>5}  "
                f"{m.host:<16} {(m.reported_version or '-'):<10} {checked}"
            )

    def _warn_about_gaps(self, machines, active_only):
        """A lane with no address is a booth this deploy will silently skip.

        This is the whole risk of sourcing the list from the database: it is only
        as complete as what has been recorded. Naming the gaps on stderr is what
        keeps "deployed to everything" honest.
        """
        known = {m.lane_id for m in machines}
        lanes = TollLane.objects.select_related('plaza').order_by(
            'plaza__plaza_id', 'lane_number',
        )
        if active_only:
            lanes = lanes.filter(is_active=True)

        missing = [lane for lane in lanes if lane.id not in known]
        if missing:
            self.stderr.write(
                f"WARNING: {len(missing)} lane(s) have no booth address recorded and "
                f"will NOT be deployed to:"
            )
            for lane in missing:
                self.stderr.write(f"  {lane.plaza.name} lane {lane.lane_number}")
            self.stderr.write(
                "Record them in the portal (Booth Code Updates), or run:\n"
                "  python manage.py discover_booths <ip> [<ip>...]"
            )

        if not active_only:
            inactive = [m for m in machines if not m.lane.is_active]
            if inactive:
                self.stderr.write(
                    f"NOTE: {len(inactive)} booth(s) belong to deactivated lanes and are "
                    "included anyway: " + ', '.join(m.host for m in inactive)
                )

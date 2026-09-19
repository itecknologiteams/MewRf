"""Runs on MASTER. Asks each booth which lane it is, and records its address.

This is how the database becomes the authoritative lane→address map without
anyone having to reconstruct it by hand. A bare list of IPs does not say which
lane each machine runs — but every booth already knows, because run_gate reads
plaza_id and lane_number out of its own rfid_config.ini. So ask the booths.

One-time migration from the old hard-coded list:

    python manage.py discover_booths --from-file booths.txt

after which deploy_booths.sh reads the list back out of master (list_booths) and
its own copy of the addresses can go.

Re-runnable: a booth that has moved to a new IP is simply re-recorded against
the same lane.
"""

import configparser
import io

from django.core.management.base import BaseCommand, CommandError

from apps.tolls import booth_deploy
from apps.tolls.models import BoothMachine, Plaza, TollLane

REMOTE_CONFIG = 'mtag_backend/rfid_config.ini'


class Command(BaseCommand):
    help = "SSH to each booth, read its lane from rfid_config.ini, and record its address."

    def add_arguments(self, parser):
        parser.add_argument('hosts', nargs='*', help="Booth IPs or hostnames.")
        parser.add_argument(
            '--from-file',
            help="File with one host per line ('#' comments and blanks ignored).",
        )
        parser.add_argument(
            '--ssh-port', type=int, default=22,
            help="SSH port for every booth in this run (default 22).",
        )
        parser.add_argument(
            '--create-lanes', action='store_true',
            help="Create a TollLane a booth reports but the database does not have.",
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Report what would be recorded without writing anything.",
        )

    def handle(self, *args, **options):
        hosts = list(options['hosts'])
        if options['from_file']:
            hosts += self._read_host_file(options['from_file'])
        # An IP repeated in the input would otherwise be probed twice and the
        # second pass would look like a lane conflict with itself.
        hosts = list(dict.fromkeys(h.strip() for h in hosts if h.strip()))
        if not hosts:
            raise CommandError("No hosts given. Pass them as arguments or use --from-file.")

        if not booth_deploy.sshpass_available():
            raise CommandError(
                "BOOTH_SSH_PASSWORD is set but sshpass is not installed on master.\n"
                "  sudo apt-get install -y sshpass"
            )

        self.dry_run = options['dry_run']
        if self.dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — nothing will be written\n"))

        # lane id → host, for lanes claimed DURING THIS RUN. Deliberately not
        # seeded from the database: an existing row holding a different address
        # is the ordinary "this booth was re-addressed" case, and overwriting it
        # is the point of re-running. Two live booths in one run reporting the
        # same lane is the real conflict, and only that is refused.
        claimed = {}
        results = []
        for host in hosts:
            results.append(self._discover(host, options, claimed))

        self._summarise(results)
        return None

    # ── One booth ────────────────────────────────────────────────────────────

    def _discover(self, host, options, claimed):
        self.stdout.write(f"--- {host} ---")
        probe = BoothMachine(host=host, ssh_port=options['ssh_port'], ssh_user='')

        result = booth_deploy.ssh(probe, f'cat {REMOTE_CONFIG} 2>/dev/null', timeout=30)
        if result.returncode != 0:
            return self._fail(host, "unreachable", result.stderr.strip().splitlines()[-1:] or [''])
        if not result.stdout.strip():
            return self._fail(host, "no rfid_config.ini", ["booth not provisioned yet"])

        try:
            plaza_id, lane_number = self._parse(result.stdout)
        except ValueError as exc:
            return self._fail(host, "bad config", [str(exc)])

        try:
            plaza = Plaza.objects.get(plaza_id=plaza_id)
        except Plaza.DoesNotExist:
            return self._fail(host, "unknown plaza", [f"plaza_id {plaza_id} is not in the database"])

        lane = TollLane.objects.filter(plaza=plaza, lane_number=lane_number).first()
        if lane is None:
            if not options['create_lanes']:
                return self._fail(
                    host, "unknown lane",
                    [f"{plaza.name} has no lane {lane_number} — re-run with --create-lanes"],
                )
            if not self.dry_run:
                lane = TollLane.objects.create(plaza=plaza, lane_number=lane_number)
            self.stdout.write(self.style.WARNING(f"    created lane {lane_number} at {plaza.name}"))

        # Two booths reporting the same lane means one of them is misconfigured;
        # recording the second would silently overwrite the first.
        other = claimed.get(getattr(lane, 'id', None))
        if other and other != host:
            return self._fail(
                host, "lane conflict",
                [f"{plaza.name} lane {lane_number} is already recorded as {other}"],
            )

        # Re-addressing is normal, but it should not happen silently — a booth
        # that moved without anyone expecting it is worth seeing.
        previous = BoothMachine.objects.filter(lane=lane).values_list('host', flat=True).first()
        if previous and previous != host:
            self.stdout.write(self.style.WARNING(f"    was {previous}"))

        if not self.dry_run:
            BoothMachine.objects.update_or_create(
                lane=lane,
                defaults={'host': host, 'ssh_port': options['ssh_port']},
            )
        claimed[lane.id] = host

        self.stdout.write(self.style.SUCCESS(
            f"    {plaza.name} lane {lane_number}"
        ))
        return ('ok', host, f"{plaza.name} lane {lane_number}")

    def _parse(self, raw):
        parser = configparser.ConfigParser()
        # Booth configs use ';' comments and may carry inline ones.
        parser.read_file(io.StringIO(raw))
        if not parser.has_section('gate'):
            raise ValueError("no [gate] section")

        plaza_raw = (parser.get('gate', 'plaza_id', fallback='') or '').strip()
        lane_raw = (parser.get('gate', 'lane_number', fallback='') or '').strip()
        if not plaza_raw:
            raise ValueError("plaza_id is blank")
        if not lane_raw:
            raise ValueError("lane_number is blank")
        try:
            # run_gate refuses to start on a UUID here; the same value is
            # meaningless to us, so say so rather than crashing on int().
            return int(plaza_raw), int(lane_raw)
        except ValueError:
            raise ValueError(
                f"plaza_id/lane_number must be integers, got '{plaza_raw}'/'{lane_raw}'"
            ) from None

    def _fail(self, host, reason, detail):
        for line in detail:
            if line:
                self.stdout.write(self.style.ERROR(f"    {line}"))
        return ('skip', host, reason)

    def _summarise(self, results):
        ok = [r for r in results if r[0] == 'ok']
        skipped = [r for r in results if r[0] != 'ok']

        self.stdout.write("")
        self.stdout.write("=" * 56)
        self.stdout.write(f"  recorded {len(ok)}, skipped {len(skipped)}")
        self.stdout.write("=" * 56)
        for _, host, what in ok:
            self.stdout.write(f"  OK    {host:<16} {what}")
        for _, host, why in skipped:
            self.stdout.write(self.style.ERROR(f"  SKIP  {host:<16} {why}"))
        if skipped:
            self.stdout.write("")
            self.stdout.write(
                "Skipped booths have NO address recorded, so deploy_booths.sh will not\n"
                "reach them. Fix the cause and re-run, or set the address by hand in the\n"
                "portal under Booth Code Updates."
            )

    def _read_host_file(self, path):
        try:
            with open(path, encoding='utf-8') as handle:
                lines = handle.read().splitlines()
        except OSError as exc:
            raise CommandError(f"Could not read {path}: {exc}") from None
        return [
            line.split('#')[0].strip().strip('"').strip("'")
            for line in lines
            if line.split('#')[0].strip()
        ]

"""
Install the operator's canonical plaza list (apps/tolls/plaza_registry.py).

    python manage.py load_plazas                  # show what would change
    python manage.py load_plazas --apply          # create/update the 9 plazas
    python manage.py load_plazas --apply --drop-legacy
    python manage.py load_plazas --apply --lanes 6

Run this on MASTER only. Booths receive plazas through the sync service's
pull_reference pass — never load them locally, or the booth invents rows with
different UUIDs than master's and the first pull collides.

Dry-run by default: it prints the plan and changes nothing until --apply.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.tolls.models import FareMatrix, Plaza, TollLane, TollRate
from apps.tolls.plaza_registry import (
    LANES, LEGACY_PLAZA_ID_BASE, PLAZAS, format_plaza_id,
)


class Command(BaseCommand):
    help = "Install the canonical plaza list on master (see plaza_registry.py)."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', default=False,
                            help='Actually write. Without it this is a dry run.')
        parser.add_argument('--lanes', type=int, default=None,
                            help='DEPRECATED and ignored. Lane numbers come from '
                                 'LANES in plaza_registry.py — they are the real '
                                 'installed numbers, not a count from 1.')
        parser.add_argument('--prune-lanes', action='store_true', default=False,
                            help='Delete lanes that are NOT in the registry (e.g. the '
                                 'lanes 1..4 the old --lanes seeding invented). Trips '
                                 'keep their rows; their lane reference becomes NULL.')
        parser.add_argument('--drop-legacy', action='store_true', default=False,
                            help=f'Delete plazas with plaza_id >= {LEGACY_PLAZA_ID_BASE} '
                                 '(the pre-existing rows migration 0007 renumbered) '
                                 'and every toll rate referencing them.')

    def handle(self, *args, **options):
        apply_changes = options['apply']
        lane_count    = options['lanes']
        prune_lanes   = options['prune_lanes']
        drop_legacy   = options['drop_legacy']
        ok, warn, err = self.style.SUCCESS, self.style.WARNING, self.style.ERROR

        self.stdout.write("=== Canonical plaza list ===")

        legacy = Plaza.objects.filter(plaza_id__gte=LEGACY_PLAZA_ID_BASE).order_by('plaza_id')
        # Legacy pricing lives in two places: the current fare_matrix and the
        # retired toll_rates table. Both are cleaned up so a dropped plaza leaves
        # no orphan fares behind.
        legacy_fares = (FareMatrix.objects.filter(from_plaza__in=legacy) |
                        FareMatrix.objects.filter(to_plaza__in=legacy)).distinct()
        legacy_rates = (TollRate.objects.filter(entry_plaza__in=legacy) |
                        TollRate.objects.filter(exit_plaza__in=legacy)).distinct()
        legacy_rate_count = legacy_fares.count() + legacy_rates.count()

        # Refuse to delete anything a real trip points at — PROTECT would raise
        # anyway, but a clear message beats an IntegrityError traceback.
        from apps.tolls.models import TollTrip
        blocked = TollTrip.objects.filter(entry_plaza__in=legacy).exists() or \
                  TollTrip.objects.filter(exit_plaza__in=legacy).exists()

        if lane_count is not None:
            self.stdout.write(warn(
                "  --lanes is ignored: lane numbers now come from LANES in "
                "plaza_registry.py, because the real ones are sparse (plaza 001 "
                "is 4,5,10,11,12,13) and never a 1..N count."
            ))

        for plaza_id, name in PLAZAS:
            existing = Plaza.objects.filter(plaza_id=plaza_id).first()
            if existing is None:
                verb = 'CREATE'
            elif existing.name != name:
                verb = f'RENAME (was "{existing.name}")'
            else:
                verb = 'ok'
            wanted = LANES.get(plaza_id, ())
            lanes_txt = ','.join(str(n) for n in wanted) or '(none)'
            self.stdout.write(f"  {format_plaza_id(plaza_id)}  {name:<32} {verb}")
            self.stdout.write(f"        lanes: {lanes_txt}")
            if existing is not None:
                have = set(existing.lanes.values_list('lane_number', flat=True))
                missing = sorted(set(wanted) - have)
                stale = sorted(have - set(wanted))
                if missing:
                    self.stdout.write(f"        to add:  {','.join(map(str, missing))}")
                if stale:
                    self.stdout.write(warn(
                        f"        not in registry: {','.join(map(str, stale))}"
                        f"{' — will be DELETED' if prune_lanes else ' (pass --prune-lanes to remove)'}"
                    ))

        if legacy:
            self.stdout.write("")
            self.stdout.write(warn(
                f"  legacy plazas (plaza_id >= {LEGACY_PLAZA_ID_BASE}): {legacy.count()}, "
                f"referenced by {legacy_rate_count} toll rate(s)"
            ))
            for p in legacy:
                self.stdout.write(warn(f"    {p.plaza_id}  {p.name}"))
            if drop_legacy and blocked:
                self.stdout.write(err(
                    "  REFUSING --drop-legacy: real trips reference these plazas. "
                    "Reassign or archive those trips first."
                ))
                drop_legacy = False
            elif not drop_legacy:
                self.stdout.write(warn(
                    "  pass --drop-legacy to remove them and their rates"
                ))

        if not apply_changes:
            self.stdout.write("")
            self.stdout.write(warn("DRY RUN — nothing written. Re-run with --apply."))
            return

        with transaction.atomic():
            created = renamed = lanes_pruned = 0
            for plaza_id, name in PLAZAS:
                plaza, was_created = Plaza.objects.update_or_create(
                    plaza_id=plaza_id,
                    defaults={'name': name, 'is_active': True},
                )
                created += int(was_created)
                renamed += int(not was_created)
                # The operator's real lane numbers, not 1..N. A plaza absent from
                # LANES gets no lanes rather than invented ones.
                for lane_no in LANES.get(plaza_id, ()):
                    TollLane.objects.get_or_create(plaza=plaza, lane_number=lane_no)
                if prune_lanes:
                    stale = TollLane.objects.filter(plaza=plaza).exclude(
                        lane_number__in=LANES.get(plaza_id, ())
                    )
                    lanes_pruned += stale.count()
                    # Every FK to TollLane is SET_NULL, so trips and their money
                    # survive; only the record of which lane was used is lost.
                    stale.delete()

            dropped_plazas = dropped_rates = 0
            if drop_legacy:
                # Rates first: TollRate FKs plazas with CASCADE, but deleting them
                # explicitly makes the count reportable instead of silent.
                dropped_rates = (legacy_fares.delete()[0]
                                 + legacy_rates.delete()[0])
                dropped_plazas = legacy.count()
                legacy.delete()

        self.stdout.write("")
        self.stdout.write(ok(
            f"Applied — {created} created, {renamed} updated, "
            f"{sum(len(v) for v in LANES.values())} lane(s) ensured "
            f"across {len(LANES)} plaza(s)"
        ))
        if prune_lanes:
            self.stdout.write(ok(f"Pruned {lanes_pruned} lane(s) not in the registry"))
        if drop_legacy:
            self.stdout.write(ok(
                f"Removed {dropped_plazas} legacy plaza(s) and {dropped_rates} rate row(s)"
            ))

        # fare_matrix is what ExitService prices from — counting toll_rates here
        # would report "fares exist" off a table nothing charges from.
        if FareMatrix.objects.count() == 0:
            self.stdout.write(err(
                "\nNO FARES EXIST in fare_matrix. Entry will work, but every exit "
                "will be refused with 'Toll rate not configured for this route'. "
                "Run: python manage.py load_fares --apply"
            ))

        self.stdout.write("\nBooths pull these via the sync service. Point each booth at "
                          "its plaza with PLAZA_ID in deploy_booth.sh:")
        for p in Plaza.objects.order_by('plaza_id'):
            self.stdout.write(f"  PLAZA_ID={p.plaza_id:<5} {format_plaza_id(p.plaza_id)}  {p.name}")

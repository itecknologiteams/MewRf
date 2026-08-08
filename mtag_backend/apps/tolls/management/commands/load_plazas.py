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
    LEGACY_PLAZA_ID_BASE, PLAZAS, format_plaza_id,
)


class Command(BaseCommand):
    help = "Install the canonical plaza list on master (see plaza_registry.py)."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', default=False,
                            help='Actually write. Without it this is a dry run.')
        parser.add_argument('--lanes', type=int, default=4,
                            help='Lanes to ensure per plaza, numbered 1..N (default 4). '
                                 'Existing lanes are never removed.')
        parser.add_argument('--drop-legacy', action='store_true', default=False,
                            help=f'Delete plazas with plaza_id >= {LEGACY_PLAZA_ID_BASE} '
                                 '(the pre-existing rows migration 0007 renumbered) '
                                 'and every toll rate referencing them.')

    def handle(self, *args, **options):
        apply_changes = options['apply']
        lane_count    = options['lanes']
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

        for plaza_id, name in PLAZAS:
            existing = Plaza.objects.filter(plaza_id=plaza_id).first()
            if existing is None:
                verb = 'CREATE'
            elif existing.name != name:
                verb = f'RENAME (was "{existing.name}")'
            else:
                verb = 'ok'
            self.stdout.write(f"  {format_plaza_id(plaza_id)}  {name:<32} {verb}")

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
            created = renamed = 0
            for plaza_id, name in PLAZAS:
                plaza, was_created = Plaza.objects.update_or_create(
                    plaza_id=plaza_id,
                    defaults={'name': name, 'is_active': True},
                )
                created += int(was_created)
                renamed += int(not was_created)
                for lane_no in range(1, lane_count + 1):
                    TollLane.objects.get_or_create(plaza=plaza, lane_number=lane_no)

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
            f"{lane_count} lane(s) ensured per plaza"
        ))
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

"""
Seed vehicle_categories and build the fare_matrix. MASTER ONLY.

    python manage.py load_fares                    # dry run
    python manage.py load_fares --categories-only --apply
    python manage.py load_fares --apply            # categories + full matrix
    python manage.py load_fares --apply --flat 100 # every pair at one fare (testing)

Booths receive both tables through the sync service — never load them on a booth
or it invents rows with different UUIDs than master's.

The matrix is (from_plaza, to_plaza, category_index) -> fare, both directions per
pair, so an asymmetric fare stays representable.

Pricing comes from fare_registry:

  * By default the flat TARIFF — one fare per category, every plaza pair.
  * If FULL_LENGTH and SEGMENT are both filled in, distance-banded Partial/Full
    pricing is used instead, automatically.

A HALF-configured banding (one filled, the other empty) is rejected rather than
silently falling back to flat, because that would price some trips from one
table and some from another.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.tolls.fare_registry import (
    CATEGORIES, FULL_LENGTH, PARTIAL_LENGTH, SEGMENT, TARIFF,
    is_complete, zoning_configured,
)
from apps.tolls.models import FareMatrix, Plaza
from apps.tolls.plaza_registry import format_plaza_id
from apps.vehicles.models import VehicleCategory


class Command(BaseCommand):
    help = "Seed vehicle categories and build the fare matrix (master only)."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', default=False,
                            help='Actually write. Without it this is a dry run.')
        parser.add_argument('--categories-only', action='store_true', default=False,
                            help='Seed vehicle_categories and stop.')
        parser.add_argument('--flat', type=float, default=None,
                            help='Testing only: charge this fare for EVERY plaza pair '
                                 'and category, ignoring the Partial/Full split.')

    # ── categories ────────────────────────────────────────────────────────────

    def _sync_categories(self, apply_changes):
        self.stdout.write("=== Vehicle categories ===")
        for index, code, name, description in CATEGORIES:
            existing = VehicleCategory.objects.filter(category_index=index).first()
            verb = 'ok' if existing and existing.name == name else (
                'CREATE' if existing is None else 'UPDATE')
            self.stdout.write(f"  {index}  {code:<12} {name:<28} {verb}")
            if apply_changes:
                VehicleCategory.objects.update_or_create(
                    category_index=index,
                    defaults={'code': code, 'name': name,
                              'description': description, 'is_active': True},
                )

    # ── fare selection ────────────────────────────────────────────────────────

    def _fare_for(self, from_plaza, to_plaza, index, flat):
        if flat is not None:
            return flat

        # Flat tariff (the current configuration): one fare per category, applied
        # to every plaza pair. See fare_registry.TARIFF.
        if not zoning_configured():
            return TARIFF[index]

        # Distance-banded: Partial when both plazas sit on the same side of
        # Quaidabad, Full when the trip crosses it.
        a = SEGMENT.get(from_plaza.plaza_id)
        b = SEGMENT.get(to_plaza.plaza_id)
        if a is None or b is None:
            unmapped = from_plaza if a is None else to_plaza
            raise CommandError(
                f"fare_registry.SEGMENT has no entry for plaza "
                f"{format_plaza_id(unmapped.plaza_id)} ({unmapped.name})"
            )
        crosses = {a, b} == {'qayumabad_side', 'm9_side'}
        table = FULL_LENGTH if crosses else PARTIAL_LENGTH
        if index not in table:
            raise CommandError(
                f"no {'FULL' if crosses else 'PARTIAL'} fare for category_index {index}"
            )
        return table[index]

    # ── entry point ───────────────────────────────────────────────────────────

    def handle(self, *args, **options):
        apply_changes = options['apply']
        flat          = options['flat']
        ok, warn, err = self.style.SUCCESS, self.style.WARNING, self.style.ERROR

        self._sync_categories(apply_changes)

        if options['categories_only']:
            self.stdout.write("" if apply_changes else warn("\nDRY RUN — re-run with --apply."))
            return

        plazas = list(Plaza.objects.order_by('plaza_id'))
        if len(plazas) < 2:
            raise CommandError(
                f"need at least 2 plazas, found {len(plazas)}. "
                "Run `manage.py load_plazas --apply` first."
            )

        if flat is None:
            complete, missing = is_complete()
            if not complete:
                self.stdout.write("")
                self.stdout.write(err("Cannot build the fare matrix yet:"))
                for m in missing:
                    self.stdout.write(err(f"  - {m}"))
                self.stdout.write(warn(
                    "\nFill these in at apps/tolls/fare_registry.py, or pass --flat N "
                    "to load a single testing fare for every pair."
                ))
                raise CommandError("fare_registry is incomplete")

        indexes = [c[0] for c in CATEGORIES]
        # Same-plaza pairs (A -> A) ARE included: a vehicle that enters and
        # exits at the same plaza is charged the same fare as any other trip.
        # Without a row for (A, A) the exit is refused with 'Toll rate not
        # configured for this route' and the barrier stays shut.
        pairs = [(a, b) for a in plazas for b in plazas]
        total = len(pairs) * len(indexes)

        self.stdout.write("")
        self.stdout.write(f"=== Fare matrix: {len(plazas)} plazas x {len(indexes)} categories ===")
        self.stdout.write(f"  {len(pairs)} directed plaza pairs (incl. same-plaza) -> {total} fare rows")
        if flat is not None:
            self.stdout.write(warn(
                f"  --flat {flat} for every row — testing only, not the notified tariff"
            ))
        elif zoning_configured():
            self.stdout.write("  pricing: distance-banded (Partial / Full across Quaidabad)")
        else:
            self.stdout.write("  pricing: single tariff, same fare for every plaza pair")
            for index, code, name, _ in CATEGORIES:
                self.stdout.write(f"    {index}  {name:<28} {TARIFF[index]}")

        if not apply_changes:
            self.stdout.write(warn("\nDRY RUN — nothing written. Re-run with --apply."))
            return

        categories = {c.category_index: c for c in VehicleCategory.objects.all()}
        written = 0
        with transaction.atomic():
            for from_plaza, to_plaza in pairs:
                for index in indexes:
                    FareMatrix.objects.update_or_create(
                        from_plaza=from_plaza,
                        to_plaza=to_plaza,
                        category=categories[index],
                        defaults={'fare': self._fare_for(from_plaza, to_plaza, index, flat)},
                    )
                    written += 1

        self.stdout.write(ok(f"\nApplied — {written} fare rows in fare_matrix"))
        self.stdout.write(
            f"  categories: {VehicleCategory.objects.count()}  "
            f"fares: {FareMatrix.objects.count()}"
        )

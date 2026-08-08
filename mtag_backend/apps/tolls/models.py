import uuid
from django.db import models
from apps.vehicles.models import VehicleType
from apps.tolls.plaza_registry import format_plaza_id


class Plaza(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Operator-assigned plaza number. This is the identifier humans and booth
    # configs use (replaced the old `code` CharField). NOT the same thing as
    # `id` above, and NOT the same thing as the `plaza_id` FK column Django
    # generates on TollLane/TollRate/TollTrip — those hold this row's UUID.
    plaza_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=100)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'plazas'

    @property
    def display_id(self) -> str:
        """plaza_id as the operator writes it: 1 -> '001'. Display only."""
        return format_plaza_id(self.plaza_id)

    def __str__(self):
        return f"{self.name} ({self.display_id})"


class TollLane(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plaza = models.ForeignKey(Plaza, on_delete=models.CASCADE, related_name='lanes')
    lane_number = models.IntegerField()
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'toll_lanes'
        unique_together = ('plaza', 'lane_number')

    def __str__(self):
        return f"{self.plaza.display_id} — Lane {self.lane_number}"


class TollRate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entry_plaza = models.ForeignKey(Plaza, on_delete=models.CASCADE, related_name='entry_rates')
    exit_plaza = models.ForeignKey(Plaza, on_delete=models.CASCADE, related_name='exit_rates')
    vehicle_type = models.CharField(max_length=20, choices=VehicleType.choices)
    rate = models.DecimalField(max_digits=8, decimal_places=2)
    peak_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=1.0)
    effective_from = models.DateField()

    class Meta:
        db_table = 'toll_rates'
        ordering = ['-effective_from']
        unique_together = ('entry_plaza', 'exit_plaza', 'vehicle_type', 'effective_from')

    def __str__(self):
        return f"{self.entry_plaza.display_id}→{self.exit_plaza.display_id} — {self.vehicle_type} Rs.{self.rate}"


class FareMatrix(models.Model):
    """Fare for one (from_plaza, to_plaza, vehicle category) combination.

    Replaces the hardcoded TollRate approach: fares are data an operator can
    revise, not values baked into a fare table in code.

    `category` is a FK declared with to_field/db_column so the physical column is
    literally `category_index` (matching vehicle_categories.category_index) while
    still giving real referential integrity — `fare.category` is the object and
    `fare.category_id` is the integer index.

    Direction matters: (A -> B) and (B -> A) are separate rows, so an asymmetric
    fare is representable. `load_fares` writes both directions.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    from_plaza = models.ForeignKey(
        Plaza, on_delete=models.CASCADE, related_name='fares_from'
    )
    to_plaza = models.ForeignKey(
        Plaza, on_delete=models.CASCADE, related_name='fares_to'
    )
    category = models.ForeignKey(
        'vehicles.VehicleCategory',
        to_field='category_index',
        db_column='category_index',
        on_delete=models.PROTECT,
        related_name='fares',
    )
    fare = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'fare_matrix'
        unique_together = ('from_plaza', 'to_plaza', 'category')
        indexes = [
            # The exact lookup ExitService does on every vehicle. Named
            # explicitly so it matches migration 0009 — without a name Django
            # autogenerates one and then wants to rename it on every check.
            models.Index(fields=['from_plaza', 'to_plaza', 'category'],
                         name='idx_fare_from_to_cat'),
        ]
        verbose_name_plural = 'fare matrix'

    def __str__(self):
        return (f"{self.from_plaza.display_id}->{self.to_plaza.display_id} "
                f"cat{self.category_id} Rs.{self.fare}")


class TripStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'


class TollTrip(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicle = models.ForeignKey('vehicles.Vehicle', on_delete=models.PROTECT, related_name='trips')
    tag = models.ForeignKey('vehicles.Tag', on_delete=models.PROTECT, related_name='trips')
    account = models.ForeignKey('accounts.Account', on_delete=models.PROTECT, related_name='trips')
    entry_plaza = models.ForeignKey(Plaza, on_delete=models.PROTECT, related_name='entry_trips')
    entry_lane = models.ForeignKey(
        TollLane, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='entry_trips'
    )
    entry_time = models.DateTimeField(auto_now_add=True)
    exit_plaza = models.ForeignKey(
        Plaza, null=True, blank=True,
        on_delete=models.PROTECT, related_name='exit_trips'
    )
    exit_lane = models.ForeignKey(
        TollLane, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='exit_trips'
    )
    exit_time = models.DateTimeField(null=True, blank=True)
    charge_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    balance_before = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=TripStatus.choices, default=TripStatus.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'toll_trips'
        indexes = [
            models.Index(fields=['vehicle', 'status']),
            models.Index(fields=['entry_time']),
            models.Index(fields=['updated_at']),
            models.Index(fields=['entry_plaza', 'entry_time']),
            models.Index(
                fields=['exit_plaza', 'exit_time'],
                name='idx_trips_exit_plaza_time',
                condition=models.Q(status='completed'),
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['vehicle'],
                condition=models.Q(status='active'),
                name='unique_active_trip_per_vehicle'
            )
        ]

    def __str__(self):
        return f"{self.vehicle.plate_number} — {self.status}"


class DailySummary(models.Model):
    """Pre-aggregated daily booth-wise totals. Updated atomically on every entry/exit.
    Reports read from this table instead of scanning all toll_trips."""
    date         = models.DateField(db_index=True)
    plaza        = models.ForeignKey(Plaza, on_delete=models.CASCADE, related_name='daily_summaries')
    lane         = models.ForeignKey(TollLane, null=True, blank=True, on_delete=models.SET_NULL, related_name='daily_summaries')
    vehicle_type = models.CharField(max_length=20)
    entries      = models.IntegerField(default=0)
    exits        = models.IntegerField(default=0)
    revenue      = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        db_table = 'daily_summaries'
        unique_together = ('date', 'plaza', 'lane', 'vehicle_type')
        indexes = [models.Index(fields=['date', 'plaza'])]

    def __str__(self):
        return f"{self.date} | {self.plaza} | lane={self.lane_id} | {self.vehicle_type}"


class SyncLog(models.Model):
    """Tracks last successful sync timestamp per table per direction."""
    table_name   = models.CharField(max_length=60, unique=True)
    last_pull_at = models.DateTimeField(null=True, blank=True)
    last_push_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'sync_log'

    def __str__(self):
        return self.table_name


class PendingGateOpen(models.Model):
    """Created by the HTTP API when entry/exit succeeds via portal.
    run_gate.py polls this table and opens the barrier when it finds a record for its plaza."""
    plaza = models.ForeignKey(Plaza, on_delete=models.CASCADE, related_name='pending_opens')
    lane = models.ForeignKey(TollLane, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    executed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'pending_gate_opens'

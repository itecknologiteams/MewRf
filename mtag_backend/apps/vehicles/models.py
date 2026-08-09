from django.db import models


class VehicleType(models.TextChoices):
    """Fare classes from the Shahra-e-Bhutto toll notification (Column 2).

    One choice per notified fare class — the earlier generic 'bus'/'truck' could
    not distinguish a Wagon (150) from a Large Bus (250), or a 2-axle truck (350)
    from a 4-axle (450), so every such vehicle was billed at one arbitrary rate.

    Value strings are what land in the database and in TollRate.vehicle_type;
    labels mirror the notification's wording so operators can match them to the
    printed schedule.
    """
    CAR         = 'car',         'Car / Jeep / Taxi / Pickup'
    WAGON       = 'wagon',       'Wagon / Hiace'
    COACH       = 'coach',       'Coach / Coaster / Mini Bus'
    LARGE_BUS   = 'large_bus',   'Large Bus'
    TRUCK_2AXLE = 'truck_2axle', '2 Axle Truck'
    TRUCK_3AXLE = 'truck_3axle', '3 Axle Truck'
    TRUCK_4AXLE = 'truck_4axle', '4 or More Axle Truck'
    # Not permitted on the expressway, but kept as a valid registration class so
    # a motorcycle can be recorded and refused rather than mis-billed as a car.
    MOTORCYCLE  = 'motorcycle',  'Motorcycle'


class VehicleCategory(models.Model):
    """Billing category for a vehicle — the notification's Column 2 classes.

    Fares live in the database (see tolls.FareMatrix), not in code, so the
    operator can revise a rate without a deployment. `category_index` is the
    stable business key the fare matrix joins on; `code` mirrors the
    VehicleType choice value so an existing vehicles.vehicle_type string maps
    straight onto a category without touching the Vehicle table.
    """
    category_index = models.IntegerField(
        unique=True,
        help_text="Stable numeric key referenced by fare_matrix.category_index",
    )
    code = models.CharField(
        max_length=20, unique=True,
        help_text="Matches Vehicle.vehicle_type, e.g. 'car', 'truck_2axle'",
    )
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=255, blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'vehicle_categories'
        ordering = ['category_index']
        verbose_name_plural = 'vehicle categories'

    def __str__(self):
        return f"{self.category_index}. {self.name}"


class VehicleStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    INACTIVE = 'inactive', 'Inactive'
    SUSPENDED = 'suspended', 'Suspended'


class TagStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    EXPIRED = 'expired', 'Expired'
    SUSPENDED = 'suspended', 'Suspended'
    DEACTIVATED = 'deactivated', 'Deactivated'


class Vehicle(models.Model):
    owner = models.ForeignKey(
        'users.User', on_delete=models.PROTECT, related_name='vehicles'
    )
    plate_number = models.CharField(max_length=20, unique=True)
    vehicle_type = models.CharField(max_length=20, choices=VehicleType.choices)
    status = models.CharField(max_length=20, choices=VehicleStatus.choices, default=VehicleStatus.ACTIVE)
    registered_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'vehicles'
        indexes = [models.Index(fields=['plate_number'])]

    def __str__(self):
        return self.plate_number


class Tag(models.Model):
    tag_serial = models.CharField(max_length=24, unique=True)
    tid = models.CharField(max_length=24, null=True, blank=True, unique=True)
    epc = models.CharField(max_length=24, blank=True, default='')
    vehicle = models.OneToOneField(Vehicle, null=True, blank=True, on_delete=models.CASCADE, related_name='tag')
    issued_at = models.DateTimeField(auto_now_add=True)
    expiry_date = models.DateField()
    status = models.CharField(max_length=20, choices=TagStatus.choices, default=TagStatus.ACTIVE)
    last_scanned_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tags'
        indexes = [models.Index(fields=['tag_serial'])]

    def __str__(self):
        return self.tag_serial

    @property
    def is_valid(self):
        from django.utils import timezone
        return (
            self.vehicle_id is not None and
            self.status == TagStatus.ACTIVE and
            self.expiry_date >= timezone.now().date()
        )


class TagAssignment(models.Model):
    """History of which vehicle a tag was fitted to, and for how long.

    One row per installation period. Answers, for any tag:
      - which vehicle is it in now          -> removed_at IS NULL
      - which vehicle was it in before      -> order by assigned_at
      - when was it taken out, and why      -> removed_at, removed_reason
      - where did it go next                -> the following row

    Kept as periods rather than an event stream so "where was this tag on
    <date>" is one query instead of replaying events. `tags.vehicle` still holds
    the CURRENT assignment; this table is the audit trail behind it.

    tag_serial is denormalised so history survives a tag row being deleted —
    an audit trail that disappears with its subject is not an audit trail.
    """
    tag = models.ForeignKey(
        'Tag', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='assignments',
    )
    tag_serial = models.CharField(max_length=24, db_index=True)
    vehicle = models.ForeignKey(
        Vehicle, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='tag_assignments',
    )
    plate_number = models.CharField(max_length=20, blank=True, default='')

    assigned_at = models.DateTimeField()
    assigned_by = models.ForeignKey(
        'users.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='tag_assignments_made',
    )

    # NULL while the tag is still fitted to this vehicle.
    removed_at = models.DateTimeField(null=True, blank=True)
    removed_reason = models.CharField(max_length=120, blank=True, default='')

    notes = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tag_assignments'
        ordering = ['-assigned_at']
        indexes = [
            models.Index(fields=['tag_serial', '-assigned_at']),
            models.Index(fields=['vehicle', '-assigned_at']),
        ]
        constraints = [
            # A tag can only be fitted to one vehicle at a time.
            models.UniqueConstraint(
                fields=['tag_serial'],
                condition=models.Q(removed_at__isnull=True),
                name='unique_open_assignment_per_tag',
            ),
        ]

    def __str__(self):
        until = self.removed_at.date() if self.removed_at else 'present'
        return f"{self.tag_serial} -> {self.plate_number or '?'} ({self.assigned_at.date()}..{until})"

    @property
    def is_current(self) -> bool:
        return self.removed_at is None


class ScanBuffer(models.Model):
    """Transient per-user buffer for handheld scan sessions.

    A WiFi RFID device POSTs each detected tag here; the bulk-tags web app polls
    it to show a live list + count, then bulk-inserts the tags. Deduplicated per
    (user, tid). Cleared after insert (or manually)."""
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='scan_buffer')
    tid = models.CharField(max_length=24)
    epc = models.CharField(max_length=24, blank=True, default='')
    scanned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'scan_buffer'
        unique_together = ('user', 'tid')
        ordering = ['-scanned_at']

    def __str__(self):
        return f"{self.tid} ({self.user_id})"


class UnregisteredInventoryStatus(models.TextChoices):
    UNREGISTERED = 'unregistered', 'Unregistered'
    BOOTH_ASSIGNED = 'booth_assigned', 'Booth Assigned'
    ACTIVATED = 'activated', 'Activated'


class UnregisteredInventory(models.Model):
    """Unregistered inventory - tags waiting for booth assignment and activation."""
    tag_serial = models.CharField(max_length=50, unique=True)
    tid = models.CharField(max_length=50, unique=True)
    epc = models.CharField(max_length=100, blank=True, default='')

    vehicle_plate = models.CharField(max_length=20, null=True, blank=True)
    vehicle_type = models.CharField(max_length=20, choices=VehicleType.choices, default=VehicleType.CAR)
    vehicle_color = models.CharField(max_length=20, null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=UnregisteredInventoryStatus.choices,
        default=UnregisteredInventoryStatus.UNREGISTERED
    )

    notes = models.TextField(blank=True, default='')

    # Booth assignment
    booth_assigned_id = models.IntegerField(null=True, blank=True)  # 1-7 plaza id
    booth_assigned_at = models.DateTimeField(null=True, blank=True)

    # Activation
    first_activated_booth_id = models.IntegerField(null=True, blank=True)
    first_activated_at = models.DateTimeField(null=True, blank=True)
    activated_for_account = models.ForeignKey(
        'accounts.Account', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='activated_from_inventory'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=100, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'unregistered_inventory'
        indexes = [
            models.Index(fields=['tag_serial']),
            models.Index(fields=['tid']),
            models.Index(fields=['status']),
            models.Index(fields=['booth_assigned_id']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.tag_serial} ({self.status})"


class BoothInventoryAssignment(models.Model):
    """Track booth assignments for unregistered inventory."""
    inventory = models.ForeignKey(
        UnregisteredInventory, on_delete=models.CASCADE, related_name='booth_assignments'
    )
    booth_id = models.IntegerField()  # 1-7 plaza id

    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.CharField(max_length=100, null=True, blank=True)

    is_active = models.BooleanField(default=False)
    activated_at = models.DateTimeField(null=True, blank=True)

    notes = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'booth_inventory_assignments'
        indexes = [
            models.Index(fields=['booth_id']),
            models.Index(fields=['is_active']),
        ]
        ordering = ['-assigned_at']

    def __str__(self):
        return f"{self.inventory.tag_serial} → Booth {self.booth_id}"


class TagActivation(models.Model):
    """Record of tag activation when first scanned at booth."""
    tag_serial = models.CharField(max_length=50, unique=True)
    tid = models.CharField(max_length=50, unique=True)

    first_scan_booth_id = models.IntegerField()  # 1-7 plaza id
    first_scan_at = models.DateTimeField()

    created_account = models.ForeignKey(
        'accounts.Account', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='tag_activations'
    )

    activation_type = models.CharField(
        max_length=20,
        choices=[('auto_created', 'Auto Created'), ('linked', 'Linked to Existing')],
        default='auto_created'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tag_activations'
        indexes = [
            models.Index(fields=['tag_serial']),
            models.Index(fields=['tid']),
            models.Index(fields=['first_scan_booth_id']),
        ]
        ordering = ['-first_scan_at']

    def __str__(self):
        return f"{self.tag_serial} activated at Booth {self.first_scan_booth_id}"

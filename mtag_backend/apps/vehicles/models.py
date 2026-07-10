import uuid
from django.db import models


class VehicleType(models.TextChoices):
    CAR = 'car', 'Car'
    MOTORCYCLE = 'motorcycle', 'Motorcycle'
    TRUCK = 'truck', 'Truck'
    BUS = 'bus', 'Bus'


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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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

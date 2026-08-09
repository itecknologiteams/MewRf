import re
from datetime import date
from rest_framework import serializers
from .models import Vehicle, Tag, UnregisteredInventory, BoothInventoryAssignment, TagActivation


def normalize_plate(value: str) -> str:
    return re.sub(r'[\s\-]', '', value).upper()


class TagSerializer(serializers.ModelSerializer):
    is_valid = serializers.ReadOnlyField()

    class Meta:
        model = Tag
        fields = ['id', 'tag_serial', 'issued_at', 'expiry_date', 'status', 'last_scanned_at', 'is_valid']
        read_only_fields = ['id', 'issued_at', 'last_scanned_at']


class VehicleSerializer(serializers.ModelSerializer):
    tag = TagSerializer(read_only=True)
    owner_id = serializers.IntegerField(source='owner.id', read_only=True)
    owner_phone = serializers.CharField(source='owner.phone', read_only=True)
    owner_name = serializers.CharField(source='owner.full_name', read_only=True)
    # validators=[] drops the auto unique-validator so validate_plate_number can
    # normalize first and exclude the current instance on update.
    plate_number = serializers.CharField(max_length=20, validators=[])

    class Meta:
        model = Vehicle
        fields = ['id', 'plate_number', 'vehicle_type', 'status', 'registered_at',
                  'owner_id', 'owner_phone', 'owner_name', 'tag']
        read_only_fields = ['id', 'registered_at']

    def validate_plate_number(self, value):
        normalized = normalize_plate(value)
        if not re.match(r'^[A-Z0-9]{3,10}$', normalized):
            raise serializers.ValidationError(
                "Plate number must be 3–10 letters/digits only (e.g. LHR1234)."
            )
        qs = Vehicle.objects.filter(plate_number=normalized)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Another vehicle already has this plate number.")
        return normalized


class VehicleCreateSerializer(serializers.ModelSerializer):
    tag_serial = serializers.CharField(write_only=True)
    owner_id = serializers.IntegerField(write_only=True)
    initial_balance = serializers.DecimalField(
        max_digits=12, decimal_places=2,
        required=False, default=0,
        min_value=0,
    )

    class Meta:
        model = Vehicle
        fields = ['plate_number', 'vehicle_type', 'owner_id', 'tag_serial', 'initial_balance']

    def validate_plate_number(self, value):
        normalized = normalize_plate(value)
        if not re.match(r'^[A-Z0-9]{3,10}$', normalized):
            raise serializers.ValidationError(
                "Plate number must be 3–10 letters/digits only (e.g. LHR1234)."
            )
        return normalized

    def validate_owner_id(self, value):
        from apps.users.models import User
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError("User not found for given owner_id.")
        return value

    def validate_tag_serial(self, value):
        if not Tag.objects.filter(tag_serial=value, vehicle__isnull=True).exists():
            if Tag.objects.filter(tag_serial=value).exists():
                raise serializers.ValidationError("This tag is already assigned to another vehicle.")
            raise serializers.ValidationError("Tag not found in inventory.")
        return value

    def create(self, validated_data):
        from django.db import transaction
        from apps.accounts.models import Account
        from .models import TagStatus
        tag_serial = validated_data.pop('tag_serial')
        initial_balance = validated_data.pop('initial_balance', 0)
        with transaction.atomic():
            vehicle = Vehicle.objects.create(**validated_data)
            tag = Tag.objects.get(tag_serial=tag_serial, vehicle__isnull=True)
            tag.vehicle = vehicle
            tag.expiry_date = date(2099, 12, 31)
            tag.status = TagStatus.ACTIVE
            tag.save()
            from apps.vehicles.tag_history import open_assignment
            open_assignment(tag, vehicle, notes='initial registration')
            Account.objects.create(
                vehicle=vehicle,
                user_id=validated_data['owner_id'],
                balance=initial_balance,
            )
        return vehicle


class TagReissueSerializer(serializers.Serializer):
    tag_serial = serializers.CharField(max_length=24)

    def validate_tag_serial(self, value):
        if not Tag.objects.filter(tag_serial=value, vehicle__isnull=True).exists():
            if Tag.objects.filter(tag_serial=value).exists():
                raise serializers.ValidationError("This tag is already assigned to a vehicle.")
            raise serializers.ValidationError("Tag not found in inventory.")
        return value


# ============= Inventory Management Serializers =============

class UnregisteredInventorySerializer(serializers.ModelSerializer):
    class Meta:
        model = UnregisteredInventory
        fields = [
            'id', 'tag_serial', 'tid', 'epc',
            'vehicle_plate', 'vehicle_type', 'vehicle_color',
            'status', 'notes',
            'booth_assigned_id', 'booth_assigned_at',
            'first_activated_booth_id', 'first_activated_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class UnregisteredInventoryListSerializer(serializers.ModelSerializer):
    """Simplified list view for inventory."""
    class Meta:
        model = UnregisteredInventory
        fields = [
            'id', 'tag_serial', 'tid', 'vehicle_plate', 'vehicle_type',
            'status', 'booth_assigned_id', 'first_activated_booth_id', 'created_at'
        ]


def _validate_booth_id(value):
    """A booth id is a Plaza.plaza_id, not a 1..7 index.

    This was capped at max_value=7 from an early assumption that booths were
    numbered 1-7. The real plazas are 1, 2 and 101-107, so that cap rejected
    activation at seven of the nine booths. Validate against the plazas that
    actually exist instead of a hardcoded range.
    """
    from apps.tolls.models import Plaza
    if not Plaza.objects.filter(plaza_id=value).exists():
        known = ', '.join(str(n) for n in
                          Plaza.objects.order_by('plaza_id')
                          .values_list('plaza_id', flat=True))
        raise serializers.ValidationError(
            f"No plaza with plaza_id {value}. Known plaza_ids: {known or '(none loaded)'}"
        )
    return value


class BoothAssignmentSerializer(serializers.Serializer):
    """Serializer for booth assignment operation."""
    inventory_ids = serializers.ListField(child=serializers.IntegerField())
    booth_id = serializers.IntegerField(min_value=1, validators=[_validate_booth_id])
    assigned_by = serializers.CharField(required=False, allow_blank=True)

    def validate_inventory_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one inventory ID required.")
        if len(value) > 1000:
            raise serializers.ValidationError("Cannot assign more than 1000 tags at once.")
        return value


class TagActivationQuickCreateSerializer(serializers.Serializer):
    """Quick activation - create new account and vehicle."""
    tag_serial = serializers.CharField(max_length=50)
    tid = serializers.CharField(max_length=50)
    customer_name = serializers.CharField(max_length=100)
    customer_phone = serializers.CharField(max_length=20)
    initial_topup = serializers.DecimalField(
        max_digits=12, decimal_places=2,
        required=False, default=0,
        min_value=0
    )
    payment_method = serializers.CharField(max_length=50, default='CASH')
    activation_booth_id = serializers.IntegerField(min_value=1, validators=[_validate_booth_id])


class TagActivationLinkExistingSerializer(serializers.Serializer):
    """Activation - link to existing account."""
    tag_serial = serializers.CharField(max_length=50)
    tid = serializers.CharField(max_length=50)
    account_id = serializers.IntegerField()
    activation_booth_id = serializers.IntegerField(min_value=1, validators=[_validate_booth_id])


class TagActivationSerializer(serializers.ModelSerializer):
    """Read-only serializer for tag activation records."""
    class Meta:
        model = TagActivation
        fields = [
            'id', 'tag_serial', 'tid',
            'first_scan_booth_id', 'first_scan_at',
            'activation_type', 'created_at'
        ]
        read_only_fields = fields

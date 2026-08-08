from rest_framework import serializers
from apps.vehicles.models import VehicleCategory
from .models import FareMatrix, Plaza, TollLane, TollTrip


class TollLaneSerializer(serializers.ModelSerializer):
    class Meta:
        model = TollLane
        fields = ['id', 'lane_number', 'is_active']


class PlazaSerializer(serializers.ModelSerializer):
    lanes = TollLaneSerializer(many=True, read_only=True)

    class Meta:
        model = Plaza
        fields = ['id', 'plaza_id', 'name', 'latitude', 'longitude', 'is_active', 'lanes']


class PlazaCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plaza
        fields = ['plaza_id', 'name', 'latitude', 'longitude', 'is_active']


class LaneCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TollLane
        fields = ['lane_number', 'is_active']


class VehicleCategorySerializer(serializers.ModelSerializer):
    """Billing categories — drives the fare editor's category dropdown."""

    class Meta:
        model = VehicleCategory
        fields = ['id', 'category_index', 'code', 'name', 'description', 'is_active']


class FareSerializer(serializers.ModelSerializer):
    """Read shape for fare_matrix rows.

    `category` is exposed as the integer category_index (not the row UUID) so the
    JSON mirrors the physical fare_matrix.category_index column.
    """
    from_plaza_name = serializers.CharField(source='from_plaza.name', read_only=True)
    to_plaza_name = serializers.CharField(source='to_plaza.name', read_only=True)
    from_plaza_display_id = serializers.CharField(source='from_plaza.display_id', read_only=True)
    to_plaza_display_id = serializers.CharField(source='to_plaza.display_id', read_only=True)
    category = serializers.SlugRelatedField(
        slug_field='category_index', queryset=VehicleCategory.objects.all()
    )
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_code = serializers.CharField(source='category.code', read_only=True)

    class Meta:
        model = FareMatrix
        fields = [
            'id',
            'from_plaza', 'from_plaza_name', 'from_plaza_display_id',
            'to_plaza', 'to_plaza_name', 'to_plaza_display_id',
            'category', 'category_name', 'category_code',
            'fare', 'created_at', 'updated_at',
        ]


class FareCreateSerializer(serializers.ModelSerializer):
    category = serializers.SlugRelatedField(
        slug_field='category_index', queryset=VehicleCategory.objects.all()
    )

    class Meta:
        model = FareMatrix
        fields = ['from_plaza', 'to_plaza', 'category', 'fare']

    # NOTE: from_plaza == to_plaza is deliberately ALLOWED. A vehicle that
    # enters and exits at the same plaza is charged the same fare as any other
    # trip, so that combination needs a real row in the matrix.


class TollTripSerializer(serializers.ModelSerializer):
    entry_plaza_name = serializers.CharField(source='entry_plaza.name', read_only=True)
    exit_plaza_name = serializers.CharField(source='exit_plaza.name', read_only=True, allow_null=True)
    plate_number = serializers.CharField(source='vehicle.plate_number', read_only=True)
    duration_minutes = serializers.SerializerMethodField()

    class Meta:
        model = TollTrip
        fields = [
            'id', 'plate_number', 'entry_plaza_name', 'exit_plaza_name',
            'entry_time', 'exit_time', 'charge_amount',
            'balance_before', 'balance_after', 'status', 'duration_minutes'
        ]

    def get_duration_minutes(self, obj):
        if obj.exit_time and obj.entry_time:
            delta = obj.exit_time - obj.entry_time
            return round(delta.total_seconds() / 60, 1)
        return None

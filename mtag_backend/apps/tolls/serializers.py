from rest_framework import serializers
from apps.vehicles.models import VehicleCategory
from .models import BoothDeployJob, BoothMachine, FareMatrix, Plaza, TollLane, TollTrip


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

    def validate_lane_number(self, value):
        # Lane numbers are printed on the booth and typed into the PDA; 0 and
        # negatives are always operator error rather than a real lane.
        if value < 1:
            raise serializers.ValidationError("Lane number must be 1 or greater.")
        return value


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


class BoothMachineSerializer(serializers.ModelSerializer):
    """One row of the booth-deployment view: where the lane is, and what it runs."""

    lane_number = serializers.IntegerField(source='lane.lane_number', read_only=True)
    lane_is_active = serializers.BooleanField(source='lane.is_active', read_only=True)
    plaza_id = serializers.IntegerField(source='lane.plaza.id', read_only=True)
    plaza_name = serializers.CharField(source='lane.plaza.name', read_only=True)
    plaza_display_id = serializers.CharField(source='lane.plaza.display_id', read_only=True)
    ssh_user_effective = serializers.SerializerMethodField()
    active_job = serializers.SerializerMethodField()

    class Meta:
        model = BoothMachine
        fields = [
            'id', 'lane', 'lane_number', 'lane_is_active',
            'plaza_id', 'plaza_name', 'plaza_display_id',
            'host', 'ssh_port', 'ssh_user', 'ssh_user_effective',
            'reported_version', 'pm2_summary', 'reachable', 'last_error',
            'last_checked_at', 'last_deployed_at', 'active_job',
        ]

    def get_ssh_user_effective(self, obj):
        from django.conf import settings
        return obj.ssh_user or getattr(settings, 'BOOTH_SSH_USER', 'iteck')

    def get_active_job(self, obj):
        # Set by the list view's prefetch. The log is deliberately left out —
        # 21 rows each carrying a full deploy transcript is a huge payload for a
        # page that only needs to know a job is still running.
        job = getattr(obj, 'active_job_cached', None)
        return BoothDeployJobBriefSerializer(job).data if job else None


class BoothMachineWriteSerializer(serializers.ModelSerializer):
    # Declared explicitly to drop the UniqueValidator ModelSerializer would infer
    # from the OneToOneField. Pointing a lane at a booth is an upsert — re-saving
    # a lane must move it to the new host, not fail as a duplicate.
    lane = serializers.PrimaryKeyRelatedField(queryset=TollLane.objects.all())

    class Meta:
        model = BoothMachine
        fields = ['lane', 'host', 'ssh_port', 'ssh_user']

    def validate_host(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("A booth needs an IP or hostname.")
        return value


class BoothDeployJobBriefSerializer(serializers.ModelSerializer):
    """Job state without the transcript — for embedding in a list."""

    class Meta:
        model = BoothDeployJob
        fields = ['id', 'action', 'status', 'requested_at', 'started_at', 'finished_at']


class BoothDeployJobListSerializer(serializers.ModelSerializer):
    """Deploy history — everything but the transcript, which is fetched per job."""

    requested_by_name = serializers.CharField(source='requested_by.full_name', read_only=True)
    lane_number = serializers.IntegerField(source='machine.lane.lane_number', read_only=True)
    plaza_name = serializers.CharField(source='machine.lane.plaza.name', read_only=True)

    class Meta:
        model = BoothDeployJob
        fields = [
            'id', 'machine', 'lane_number', 'plaza_name', 'action', 'status',
            'requested_by_name', 'requested_at', 'finished_at',
            'from_version', 'to_version', 'exit_code',
        ]


class BoothDeployJobSerializer(serializers.ModelSerializer):
    requested_by_name = serializers.CharField(source='requested_by.full_name', read_only=True)
    lane_number = serializers.IntegerField(source='machine.lane.lane_number', read_only=True)

    class Meta:
        model = BoothDeployJob
        fields = [
            'id', 'machine', 'lane_number', 'action', 'status',
            'requested_by', 'requested_by_name', 'requested_at',
            'started_at', 'finished_at', 'from_version', 'to_version',
            'exit_code', 'log',
        ]

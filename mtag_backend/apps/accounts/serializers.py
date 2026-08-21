from rest_framework import serializers
from .models import Account, Transaction
from apps.vehicles.models import Vehicle


class AccountSerializer(serializers.ModelSerializer):
    plate_number = serializers.CharField(source='vehicle.plate_number', read_only=True)
    vehicle_type = serializers.CharField(source='vehicle.vehicle_type', read_only=True)

    class Meta:
        model = Account
        fields = ['id', 'vehicle_id', 'plate_number', 'vehicle_type', 'balance',
                  'balance_updated_at', 'created_at']
        read_only_fields = fields


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        # `source` is exposed because a toll deduction taken at an offline booth
        # reaches this table on the next 30s sync, so it can surface in history
        # minutes after the trip. Without source the client cannot tell a
        # late-arriving offline deduction from a real-time one, and would be
        # implying the history is live when it isn't.
        fields = [
            'id', 'transaction_type', 'amount', 'service_charge',
            'balance_before', 'balance_after',
            'status', 'source', 'tag_serial', 'reference_id', 'processed_at'
        ]
        read_only_fields = fields


class TransferSerializer(serializers.Serializer):
    source_vehicle_id = serializers.IntegerField()
    target_vehicle_id = serializers.IntegerField()
    cnic = serializers.CharField(max_length=20)
    phone = serializers.CharField(max_length=20)
    name = serializers.CharField(max_length=100)

    def validate(self, data):
        if data['source_vehicle_id'] == data['target_vehicle_id']:
            raise serializers.ValidationError("Source and target vehicle must be different.")
        return data

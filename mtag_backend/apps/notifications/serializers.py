from rest_framework import serializers

from .models import DevicePlatform, DeviceToken


class DeviceTokenRegisterSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=255)
    platform = serializers.ChoiceField(
        choices=DevicePlatform.choices, default=DevicePlatform.ANDROID
    )


class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = ['id', 'platform', 'is_active', 'created_at', 'last_used_at']
        read_only_fields = fields
        # NOTE: `token` is deliberately NOT exposed. It is a capability — anyone holding it
        # can push arbitrary notifications to that device via our FCM project — so it goes
        # in and never comes back out.

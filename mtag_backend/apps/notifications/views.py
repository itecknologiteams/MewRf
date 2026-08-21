import logging

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from utils.response import error_response, success_response

from .models import DeviceToken
from .serializers import DeviceTokenRegisterSerializer, DeviceTokenSerializer
from .services import is_configured

logger = logging.getLogger(__name__)


class DeviceRegisterView(APIView):
    """POST a device's FCM token so this user's events can reach it.

    Idempotent, and REASSIGNS rather than duplicating. FCM hands the same token to whoever
    installs next on a given device, so if a phone changes owner the token must move with it
    — otherwise the previous owner keeps receiving the new owner's balance notifications.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = DeviceTokenRegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response('Invalid data', errors=serializer.errors)

        token = serializer.validated_data['token']
        platform = serializer.validated_data['platform']

        device, created = DeviceToken.objects.update_or_create(
            token=token,
            defaults={
                'user': request.user,
                'platform': platform,
                'is_active': True,
                'last_failure': '',
            },
        )
        logger.info(
            'Device %s for user %s (%s)',
            'registered' if created else 'reassigned',
            request.user.id,
            platform,
        )
        return success_response(
            data={
                'device': DeviceTokenSerializer(device).data,
                # The app needs to know whether push actually works on this deployment. The
                # LAN build has no FCM project, and an app that shows "notifications on"
                # against a server that cannot send any is lying to the user.
                'push_available': is_configured(),
            },
            message='Device registered',
            status_code=201 if created else 200,
        )


class DeviceUnregisterView(APIView):
    """Called on sign-out, so the next user of the device does not inherit these alerts."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = (request.data.get('token') or '').strip()
        if not token:
            return error_response('token is required')
        deleted, _ = DeviceToken.objects.filter(
            token=token, user=request.user
        ).delete()
        return success_response(
            data={'removed': deleted}, message='Device unregistered'
        )


class PushStatusView(APIView):
    """Whether this deployment can deliver push, and this user's registered devices."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        devices = DeviceToken.objects.filter(user=request.user).order_by('-created_at')
        return success_response(
            data={
                'push_available': is_configured(),
                'devices': DeviceTokenSerializer(devices, many=True).data,
            }
        )

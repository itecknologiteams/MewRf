from django.urls import path

from .views import DeviceRegisterView, DeviceUnregisterView, PushStatusView

urlpatterns = [
    path('devices/register/', DeviceRegisterView.as_view(), name='device-register'),
    path('devices/unregister/', DeviceUnregisterView.as_view(), name='device-unregister'),
    path('status/', PushStatusView.as_view(), name='push-status'),
]

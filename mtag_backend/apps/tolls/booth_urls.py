"""Routes for the booth console — mounted at /booth/ on every booth.

Deliberately NOT under /api/v1/: this is a diagnostics surface for one machine,
not part of the product API that the apps and the portal are written against.
Keeping it separate means it can change shape as booths change without anything
versioned having to move with it.
"""

from django.urls import path

from .booth_console import (
    BoothBalanceView,
    BoothBarrierOpenView,
    BoothBarrierView,
    BoothCameraProbeView,
    BoothCameraSnapshotView,
    BoothCameraView,
    BoothConfigRestoreView,
    BoothConfigView,
    BoothDetectionsView,
    BoothEventsView,
    BoothLogView,
    BoothOverviewView,
    BoothRestartView,
    booth_console_page,
)

urlpatterns = [
    path('', booth_console_page, name='booth-console'),

    path('api/overview/', BoothOverviewView.as_view(), name='booth-overview'),
    path('api/config/', BoothConfigView.as_view(), name='booth-config'),
    path('api/config/restore/', BoothConfigRestoreView.as_view(),
         name='booth-config-restore'),

    path('api/detections/', BoothDetectionsView.as_view(), name='booth-detections'),
    path('api/events/', BoothEventsView.as_view(), name='booth-events'),

    path('api/barrier/', BoothBarrierView.as_view(), name='booth-barrier'),
    path('api/barrier/open/', BoothBarrierOpenView.as_view(), name='booth-barrier-open'),

    path('api/balance/', BoothBalanceView.as_view(), name='booth-balance'),

    path('api/camera/', BoothCameraView.as_view(), name='booth-camera'),
    path('api/camera/probe/', BoothCameraProbeView.as_view(), name='booth-camera-probe'),
    path('api/camera/snapshot/', BoothCameraSnapshotView.as_view(),
         name='booth-camera-snapshot'),

    path('api/logs/', BoothLogView.as_view(), name='booth-logs'),
    path('api/restart/', BoothRestartView.as_view(), name='booth-restart'),
]

from django.urls import path
from .views import (
    VehicleEntryView, VehicleExitView, TripHistoryView, MyTripListView,
    PlazaListView, TollRateListView, VehicleCategoryListView, AdminTripListView,
    AdminPlazaView, AdminPlazaDetailView, AdminLaneView,
    AdminTollRateView, AdminRateDetailView, AdminStatsView,
    AdminTripCloseView, AdminTripRefundView, AdminGateEventListView,
    AdminDailyReportView,
)

urlpatterns = [
    path('entry/', VehicleEntryView.as_view(), name='toll-entry'),
    path('exit/', VehicleExitView.as_view(), name='toll-exit'),
    path('plazas/', PlazaListView.as_view(), name='plaza-list'),
    path('rates/', TollRateListView.as_view(), name='rate-list'),
    path('vehicle-categories/', VehicleCategoryListView.as_view(), name='vehicle-category-list'),
    # BEFORE the <int:vehicle_id> route. 'my' would never match the int converter so
    # either order resolves correctly, but declaring the literal first is what keeps it
    # that way if the converter is ever widened to <str:>.
    path('trips/my/', MyTripListView.as_view(), name='my-trips'),
    path('trips/<int:vehicle_id>/', TripHistoryView.as_view(), name='trip-history'),
    path('admin/trips/', AdminTripListView.as_view(), name='admin-trips'),
    path('admin/trips/<int:trip_id>/close/', AdminTripCloseView.as_view(), name='admin-trip-close'),
    path('admin/trips/<int:trip_id>/refund/', AdminTripRefundView.as_view(), name='admin-trip-refund'),
    path('admin/stats/', AdminStatsView.as_view(), name='admin-stats'),
    path('admin/gate-events/', AdminGateEventListView.as_view(), name='admin-gate-events'),
    path('admin/daily-report/', AdminDailyReportView.as_view(), name='admin-daily-report'),
    path('admin/plazas/', AdminPlazaView.as_view(), name='admin-plaza-list'),
    path('admin/plazas/<int:pk>/', AdminPlazaDetailView.as_view(), name='admin-plaza-detail'),
    path('admin/plazas/<int:plaza_id>/lanes/', AdminLaneView.as_view(), name='admin-lane-create'),
    path('admin/rates/', AdminTollRateView.as_view(), name='admin-rate-create'),
    path('admin/rates/<int:pk>/', AdminRateDetailView.as_view(), name='admin-rate-detail'),
]

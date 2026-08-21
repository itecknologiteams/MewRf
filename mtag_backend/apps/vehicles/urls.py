from django.urls import path
from .views import (
    VehicleListCreateView, MyVehicleListView, VehicleDetailView, VehicleByPlateView, TagReissueView,
    AvailableTagsView, TagInventoryUploadView, TagCreateView, TagBulkCreateView,
    TagExistsCheckView, TagScanBufferView, ScanDebugView, VehicleSuspendView,
    InventoryUploadView, InventoryListView, BoothAssignmentView,
    TagActivationQuickCreateView, TagActivationLinkExistingView, InventoryCheckView,
)

urlpatterns = [
    path('', VehicleListCreateView.as_view(), name='vehicle-list'),
    # Before '<int:pk>/' so the literal always wins, even though 'my' could never
    # match an int converter today.
    path('my/', MyVehicleListView.as_view(), name='my-vehicles'),
    path('<int:pk>/', VehicleDetailView.as_view(), name='vehicle-detail'),
    path('<int:pk>/suspend/', VehicleSuspendView.as_view(), name='vehicle-suspend'),
    path('plate/<str:plate_number>/', VehicleByPlateView.as_view(), name='vehicle-by-plate'),
    path('tags/', TagCreateView.as_view(), name='tag-create'),
    path('tags/bulk/', TagBulkCreateView.as_view(), name='tag-bulk-create'),
    path('tags/check/', TagExistsCheckView.as_view(), name='tag-exists-check'),
    path('tags/scan/', TagScanBufferView.as_view(), name='tag-scan-buffer'),
    path('tags/scan-debug/', ScanDebugView.as_view(), name='tag-scan-debug'),
    path('tags/available/', AvailableTagsView.as_view(), name='available-tags'),
    path('tags/upload/', TagInventoryUploadView.as_view(), name='tag-upload'),
    path('tags/<int:vehicle_id>/reissue/', TagReissueView.as_view(), name='tag-reissue'),

    # Inventory Management
    path('inventory/', InventoryListView.as_view(), name='inventory-list'),
    path('inventory/upload/', InventoryUploadView.as_view(), name='inventory-upload'),
    path('inventory/assign-booth/', BoothAssignmentView.as_view(), name='booth-assignment'),
    path('inventory/activate/', TagActivationQuickCreateView.as_view(), name='tag-activate'),
    path('inventory/activate-existing/', TagActivationLinkExistingView.as_view(), name='tag-activate-existing'),
    path('inventory/check/<str:tag_serial>/', InventoryCheckView.as_view(), name='inventory-check'),
]

from django.urls import path
from .views import (
    AccountDetailView, TransactionListView, AdminAccountListView, TransferView,
    OperatorTopupView, PlateTopupView, TopupLookupView, CashTopupView,
)

urlpatterns = [
    path('vehicle/<int:vehicle_id>/', AccountDetailView.as_view(), name='account-detail'),
    path('<int:account_id>/transactions/', TransactionListView.as_view(), name='transaction-list'),
    path('admin/all/', AdminAccountListView.as_view(), name='admin-accounts'),
    path('transfer/', TransferView.as_view(), name='balance-transfer'),
    path('operator/topup/', OperatorTopupView.as_view(), name='operator-topup'),
    path('topup/plate/', PlateTopupView.as_view(), name='plate-topup'),
    path('topup/lookup/', TopupLookupView.as_view(), name='topup-lookup'),
    path('topup/cash/', CashTopupView.as_view(), name='topup-cash'),
]

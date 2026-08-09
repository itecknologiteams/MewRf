from django.urls import path
from .views import (
    InitiateTopupView, JazzCashCallbackView, TopupHistoryView,
    JazzCashInquiryView, JazzCashPaymentView,
)

urlpatterns = [
    path('topup/', InitiateTopupView.as_view(), name='initiate-topup'),
    path('jazzcash/callback/', JazzCashCallbackView.as_view(), name='jazzcash-callback'),
    # Aggregator flow (JazzCash-initiated): inquiry then payment notification.
    path('jazzcash/inquiry/', JazzCashInquiryView.as_view(), name='jazzcash-inquiry'),
    path('jazzcash/payment/', JazzCashPaymentView.as_view(), name='jazzcash-payment'),
    path('history/<int:account_id>/', TopupHistoryView.as_view(), name='topup-history'),
]

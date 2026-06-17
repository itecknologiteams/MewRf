import logging
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from utils.response import success_response, error_response
from .services import JazzCashService, verify_secure_hash
from .serializers import InitiateTopupSerializer, TopupRequestSerializer
from .models import TopupRequest

logger = logging.getLogger(__name__)


class JazzCashInquiryView(APIView):
    """JazzCash → us: look up a tag by TID, return consumer details (read-only)."""
    permission_classes = [AllowAny]

    def post(self, request):
        if not verify_secure_hash(request.data):
            return error_response("Invalid signature", status_code=401)
        result = JazzCashService.inquiry(request.data.get('tid', ''))
        if result['success']:
            return success_response(data=result, message="OK")
        return error_response(result['reason'], status_code=404)


class JazzCashPaymentView(APIView):
    """JazzCash → us: confirm a payment and credit the tag's balance (idempotent)."""
    permission_classes = [AllowAny]

    def post(self, request):
        if not verify_secure_hash(request.data):
            return error_response("Invalid signature", status_code=401)
        txn_id = request.data.get('jazzcash_txn_id', '') or request.data.get('pp_TxnRefNo', '')
        logger.info("JazzCash payment — tid:%s txn:%s", request.data.get('tid', ''), txn_id)
        result = JazzCashService.process_payment(
            tid=request.data.get('tid', ''),
            amount=request.data.get('amount'),
            jazzcash_txn_id=txn_id,
        )
        if result['success']:
            return success_response(data=result, message="Balance updated")
        return error_response(result['reason'], status_code=400)


class InitiateTopupView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = InitiateTopupSerializer(data=request.data)
        if serializer.is_valid():
            result = JazzCashService.initiate_topup(
                account_id=str(serializer.validated_data['account_id']),
                user_id=request.user.id,
                amount=serializer.validated_data['amount'],
            )
            if result['success']:
                return success_response(data=result, message="Topup initiated", status_code=201)
            return error_response(result['reason'])
        return error_response("Invalid data", errors=serializer.errors)


class JazzCashCallbackView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        txn_id = request.data.get('pp_TxnRefNo', '')
        response_code = request.data.get('pp_ResponseCode', '')
        # topup_id can come from POST body or query param (?topup_id=...)
        topup_id = request.data.get('topup_id', '') or request.query_params.get('topup_id', '')
        logger.info("JazzCash callback — txn: %s code: %s topup: %s", txn_id, response_code, topup_id)
        result = JazzCashService.handle_callback(txn_id, response_code, topup_id)
        if result['success']:
            return success_response(data=result, message="Payment recorded")
        return error_response(result['reason'], status_code=400)


class TopupHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, account_id):
        topups = TopupRequest.objects.filter(account_id=account_id).order_by('-requested_at')
        return success_response(data=TopupRequestSerializer(topups, many=True).data)

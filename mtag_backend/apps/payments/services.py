import hashlib
import hmac
import logging
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from django.db import transaction as db_transaction, IntegrityError
from django.utils import timezone
from django.conf import settings
from apps.accounts.models import (
    Account, Transaction, TransactionType, TransactionStatus, TransactionSource,
)
from .models import TopupRequest, TopupStatus

logger = logging.getLogger(__name__)


def _secure_hash(params: dict) -> str:
    """Compute JazzCash pp_SecureHash: HMAC-SHA256 over sorted non-empty values."""
    salt = settings.JAZZCASH_INTEGRITY_SALT
    sorted_values = "&".join(
        f"{k}={v}" for k, v in sorted(params.items()) if v not in (None, "")
    )
    message = f"{salt}&{sorted_values}"
    return hmac.new(
        salt.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest().upper()


def verify_secure_hash(data: dict) -> bool:
    """Verify pp_SecureHash on an incoming JazzCash request.

    Enforced only when settings.JAZZCASH_VERIFY_HASH is True. Keep it False until
    the EXACT hashing formula is confirmed with JazzCash, then turn it on (and set
    JAZZCASH_INTEGRITY_SALT). The hashing here mirrors _secure_hash; adjust to
    match JazzCash's documented algorithm once their spec is available.
    """
    if not getattr(settings, 'JAZZCASH_VERIFY_HASH', False):
        return True
    received = (data.get('pp_SecureHash') or '').upper()
    params = {k: v for k, v in data.items() if k != 'pp_SecureHash'}
    expected = _secure_hash(params)
    return bool(received) and hmac.compare_digest(received, expected)


class JazzCashService:
    # ── Aggregator flow (JazzCash-initiated) ────────────────────────────────
    # 1. inquiry(tid)        → JazzCash shows consumer details before payment
    # 2. process_payment(...) → JazzCash notifies us after the customer pays;
    #                            idempotent on jazzcash_txn_id.

    @staticmethod
    def inquiry(tid: str) -> dict:
        """Look up a tag by chip TID and return consumer details (read-only)."""
        from apps.vehicles.models import Tag, TagStatus

        norm = (tid or '').strip().replace(' ', '').upper()
        if not norm:
            return {'success': False, 'reason': 'tid is required'}
        try:
            tag = Tag.objects.select_related('vehicle__owner', 'vehicle__account').get(tid=norm)
        except Tag.DoesNotExist:
            return {'success': False, 'reason': 'Tag not found'}

        vehicle = tag.vehicle
        if vehicle is None:
            return {'success': False, 'reason': 'Tag not assigned to any vehicle'}
        if tag.status != TagStatus.ACTIVE:
            return {'success': False, 'reason': f'Tag is {tag.status}'}
        account = getattr(vehicle, 'account', None)
        if account is None:
            return {'success': False, 'reason': 'No account found for this vehicle'}

        owner = vehicle.owner
        return {
            'success': True,
            'consumer_id': str(owner.uuid),
            'vehicle_registration': vehicle.plate_number,
            'customer_name': owner.full_name,
            'tid': tag.tid,
            'current_balance': str(account.balance),
            'status': 'active',
        }

    @staticmethod
    def process_payment(tid: str, amount, jazzcash_txn_id: str) -> dict:
        """Credit a tag's balance after JazzCash confirms a payment.

        Idempotent: a repeated jazzcash_txn_id never credits twice.
        """
        from apps.vehicles.models import Tag

        norm = (tid or '').strip().replace(' ', '').upper()
        txn_id = (jazzcash_txn_id or '').strip()
        if not norm:
            return {'success': False, 'reason': 'tid is required'}
        if not txn_id:
            return {'success': False, 'reason': 'jazzcash_txn_id is required'}
        try:
            amt = Decimal(str(amount)).quantize(Decimal('0.01'))
        except (InvalidOperation, ValueError, TypeError):
            return {'success': False, 'reason': 'Invalid amount'}
        if amt <= 0:
            return {'success': False, 'reason': 'Amount must be greater than zero'}

        # Idempotency — already processed this JazzCash transaction?
        existing = (
            Transaction.objects.select_related('account')
            .filter(idempotency_key=txn_id).first()
        )
        if existing:
            logger.info("JazzCash topup duplicate ignored — txn:%s", txn_id)
            return {
                'success': True, 'already_processed': True,
                'jazzcash_txn_id': txn_id,
                'new_balance': str(existing.account.balance),
            }

        try:
            with db_transaction.atomic():
                try:
                    tag = Tag.objects.select_related('vehicle__owner').get(tid=norm)
                except Tag.DoesNotExist:
                    return {'success': False, 'reason': 'Tag not found'}
                vehicle = tag.vehicle
                if vehicle is None:
                    return {'success': False, 'reason': 'Tag not assigned to any vehicle'}
                try:
                    account = Account.objects.select_for_update().get(vehicle=vehicle)
                except Account.DoesNotExist:
                    return {'success': False, 'reason': 'No account found for this vehicle'}

                balance_before = account.balance
                account.balance += amt
                account.save(update_fields=['balance', 'balance_updated_at'])

                Transaction.objects.create(
                    account=account,
                    tag_serial=tag.tag_serial,
                    transaction_type=TransactionType.TOPUP,
                    amount=amt,
                    balance_before=balance_before,
                    balance_after=account.balance,
                    status=TransactionStatus.SUCCESS,
                    source=TransactionSource.TOPUP_JAZZCASH,
                    idempotency_key=txn_id,
                )
                topup = TopupRequest.objects.create(
                    account=account,
                    user=vehicle.owner,
                    jazzcash_txn_id=txn_id,
                    amount=amt,
                    status=TopupStatus.SUCCESS,
                    completed_at=timezone.now(),
                )
        except IntegrityError:
            # Concurrent duplicate callback — the unique txn_id lost the race.
            logger.info("JazzCash topup race duplicate — txn:%s", txn_id)
            dup = Transaction.objects.select_related('account').filter(idempotency_key=txn_id).first()
            return {
                'success': True, 'already_processed': True, 'jazzcash_txn_id': txn_id,
                'new_balance': str(dup.account.balance) if dup else None,
            }

        logger.info("JazzCash topup OK — tid:%s amount:%s txn:%s new_balance:%s",
                    norm, amt, txn_id, account.balance)
        return {
            'success': True,
            'jazzcash_txn_id': txn_id,
            'new_balance': str(account.balance),
            'topup_id': str(topup.id),
        }
    @staticmethod
    def initiate_topup(account_id: int, user_id: int, amount: Decimal) -> dict:
        if amount < Decimal('100'):
            return {'success': False, 'reason': 'Minimum top-up amount is Rs.100'}

        topup = TopupRequest.objects.create(
            account_id=account_id,
            user_id=user_id,
            amount=amount,
        )
        logger.info("Topup initiated — id: %s amount: %s", topup.id, amount)

        return_url = f"{settings.JAZZCASH_RETURN_URL}?topup_id={topup.id}"
        payload = {
            'pp_TxnRefNo': str(topup.id).replace('-', '')[:20],
            'pp_Amount': str(int(amount * 100)),
            'pp_TxnCurrency': 'PKR',
            'pp_MerchantID': settings.JAZZCASH_MERCHANT_ID,
            'pp_Password': settings.JAZZCASH_PASSWORD,
            'pp_ReturnURL': return_url,
            'topup_id': str(topup.id),
        }
        payload['pp_SecureHash'] = _secure_hash(payload)

        # pp_Password is a MERCHANT credential and must never leave the server.
        # This payload is returned to the caller — a mobile app on a stranger's
        # phone — so shipping it meant anyone who installed the app could read
        # the merchant password out of a response body and transact as us. It
        # still goes into the hash above, because that is computed here.
        #
        # Consequence: this payload is NOT a complete JazzCash Hosted Checkout
        # form (which requires pp_Password). Flow B therefore cannot be finished
        # by having the client POST this anywhere — the redirect leg has to be
        # built server-side, which is the correct shape regardless. There is also
        # no checkout URL in this response and JAZZCASH_VERIFY_HASH is off with
        # the hashing formula unconfirmed, so Flow B is incomplete either way.
        # See mtag_user_app/README.md § "What is stubbed".
        client_payload = {k: v for k, v in payload.items() if k != 'pp_Password'}
        return {'success': True, 'topup_id': str(topup.id), 'jazzcash_payload': client_payload}

    @staticmethod
    @db_transaction.atomic
    def handle_callback(jazzcash_txn_id: str, pp_response_code: str, topup_id: str) -> dict:
        if not topup_id:
            return {'success': False, 'reason': 'topup_id is required'}

        try:
            topup = TopupRequest.objects.select_for_update().get(
                id=topup_id, status=TopupStatus.PENDING
            )
        except (TopupRequest.DoesNotExist, ValidationError, ValueError):
            logger.warning("Topup not found or already processed: %s", topup_id)
            return {'success': False, 'reason': 'Topup not found or already processed'}

        topup.jazzcash_txn_id = jazzcash_txn_id

        if pp_response_code == '000':
            account = Account.objects.select_for_update().get(id=topup.account_id)
            balance_before = account.balance
            account.balance += topup.amount
            account.save(update_fields=['balance', 'balance_updated_at'])

            Transaction.objects.create(
                account=account,
                transaction_type=TransactionType.TOPUP,
                amount=topup.amount,
                balance_before=balance_before,
                balance_after=account.balance,
                status=TransactionStatus.SUCCESS,
            )

            topup.status = TopupStatus.SUCCESS
            topup.completed_at = timezone.now()
            topup.save()
            logger.info("Topup success — id: %s new_balance: %s", topup_id, account.balance)
            return {'success': True, 'new_balance': str(account.balance)}

        topup.status = TopupStatus.FAILED
        topup.save()
        logger.warning("Topup failed — id: %s code: %s", topup_id, pp_response_code)
        return {'success': False, 'reason': f'Payment failed (code: {pp_response_code})'}

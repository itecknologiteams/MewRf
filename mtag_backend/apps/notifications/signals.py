"""Money events -> push, via post_save signals.

## Why signals and not explicit calls

`Transaction.objects.create(...)` appears in **16 places** across accounts, payments and
tolls — cash top-up, operator top-up, plate top-up, the JazzCash aggregator credit, the
JazzCash callback, the exit charge, the reconciliation sweep, refunds. Calling a notifier at
each one guarantees that the next site added quietly does not notify, and that is exactly the
kind of omission nobody notices: the money still moves, the user just never hears about it.

A `post_save` receiver catches every path, present and future, including any management
command that credits an account.

## Two rules this file exists to enforce

1. **on_commit.** The receiver fires INSIDE the database transaction. Sending from there
   would push "you were charged Rs. 150" for a transaction that is about to roll back —
   `CashTopupView` and `ExitService` both do real work inside `atomic()` blocks that can
   fail after the Transaction row is written. `transaction.on_commit` defers delivery until
   the money is actually committed.

2. **Nothing propagates.** A push failure must never fail a payment. The send is already
   non-raising, and this wraps it again: a bug in message construction must not turn a
   successful top-up into a 500.
"""

import logging

from django.db import transaction as db_transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.models import Transaction, TransactionStatus, TransactionType
from apps.payments.models import TopupRequest, TopupStatus

from .services import send_to_user

logger = logging.getLogger(__name__)


def _rupees(amount) -> str:
    """`1250.00` -> `Rs. 1,250`. Whole rupees: paisa is noise in a notification."""
    try:
        return f'Rs. {int(amount):,}'
    except (TypeError, ValueError):
        return f'Rs. {amount}'


@receiver(post_save, sender=Transaction, dispatch_uid='mtag_txn_push')
def notify_transaction(sender, instance: Transaction, created: bool, **kwargs):
    if not created:
        return
    # A pending or failed row is not news the user can act on, and a failed toll would read
    # as a charge that never happened.
    if instance.status != TransactionStatus.SUCCESS:
        return

    db_transaction.on_commit(lambda: _send_transaction(instance.pk))


def _send_transaction(transaction_id: int) -> None:
    try:
        txn = (
            Transaction.objects.select_related('account__user', 'account__vehicle')
            .filter(pk=transaction_id)
            .first()
        )
        if txn is None:
            return

        account = txn.account
        plate = account.vehicle.plate_number if account.vehicle_id else ''
        amount = _rupees(txn.amount)
        balance = _rupees(txn.balance_after)

        # Wording differs per type because the user's question differs. For a deduction it is
        # "what is left"; for a credit it is "did it arrive".
        if txn.transaction_type == TransactionType.TOLL_DEDUCTION:
            title = f'Toll paid · {amount}'
            body = f'{plate} — balance now {balance}'
            # An offline booth syncs up to 30s later, so this can arrive well after the
            # driver left the plaza. Saying so prevents it reading as a duplicate charge.
            if txn.source == 'offline_exit_sync':
                body += ' (synced from booth)'
        elif txn.transaction_type == TransactionType.TOPUP:
            title = f'Top-up received · {amount}'
            body = f'{plate} — balance now {balance}'
        elif txn.transaction_type == TransactionType.REFUND:
            title = f'Refund · {amount}'
            body = f'{plate} — balance now {balance}'
        elif txn.transaction_type == TransactionType.TRANSFER_IN:
            title = f'Transfer received · {amount}'
            body = f'{plate} — balance now {balance}'
        elif txn.transaction_type == TransactionType.TRANSFER_OUT:
            title = f'Transfer sent · {amount}'
            body = f'{plate} — balance now {balance}'
        else:
            title = f'{amount}'
            body = f'{plate} — balance now {balance}'

        send_to_user(
            account.user_id,
            title=title,
            body=body,
            data={
                'type': 'transaction',
                'transaction_type': txn.transaction_type,
                'account_id': account.id,
                'vehicle_id': account.vehicle_id or '',
                # Deep link target, so tapping the notification lands on the right ledger
                # rather than the dashboard.
                'route': f'/activity?account={account.id}',
            },
        )
    except Exception:  # noqa: BLE001
        # Deliberately broad and deliberately swallowed: this runs on_commit, AFTER the money
        # moved. Raising here cannot undo the transaction — it would only surface a
        # notification bug as a payment error.
        logger.exception('Transaction push failed for %s', transaction_id)


@receiver(post_save, sender=TopupRequest, dispatch_uid='mtag_topup_push')
def notify_topup_outcome(sender, instance: TopupRequest, created: bool, **kwargs):
    """Tells the user when a PENDING top-up resolves.

    Only the failure case is pushed here. A successful one already writes a Transaction,
    which notifies above — pushing both would tell the user about the same money twice.
    """
    if created or instance.status != TopupStatus.FAILED:
        return
    db_transaction.on_commit(lambda: _send_topup_failed(instance.pk))


def _send_topup_failed(topup_id: int) -> None:
    try:
        topup = TopupRequest.objects.select_related('account__vehicle').filter(
            pk=topup_id
        ).first()
        if topup is None:
            return
        plate = (
            topup.account.vehicle.plate_number
            if topup.account_id and topup.account.vehicle_id
            else ''
        )
        send_to_user(
            topup.user_id,
            title='Top-up failed',
            body=f'{_rupees(topup.amount)} was not credited to {plate}. '
            'No money was taken.',
            data={
                'type': 'topup_failed',
                'topup_id': topup.id,
                'route': f'/topup?account={topup.account_id}',
            },
        )
    except Exception:  # noqa: BLE001
        logger.exception('Top-up failure push failed for %s', topup_id)

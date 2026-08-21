"""Push notification tests.

The important ones here are not "does a message get built" — they are the two invariants that
would cost real money or real trust if they broke:

  * a notification failure must NEVER fail the payment that triggered it;
  * a notification must NEVER be sent for a transaction that rolled back.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.db import transaction as db_transaction
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import (
    Account,
    Transaction,
    TransactionSource,
    TransactionStatus,
    TransactionType,
)
from apps.payments.models import TopupRequest, TopupStatus
from apps.users.models import User
from apps.vehicles.models import Tag, TagStatus, Vehicle

from .models import DeviceToken


def make_holder(phone='03111111111', plate='KHI1001'):
    user = User.objects.create_user(
        phone=phone, password='holderpass123', full_name='Holder'
    )
    vehicle = Vehicle.objects.create(owner=user, plate_number=plate, vehicle_type='car')
    account = Account.objects.create(
        vehicle=vehicle, user=user, balance=Decimal('1000.00')
    )
    Tag.objects.create(
        tag_serial=f'SER{plate}', tid=f'TID{plate}', vehicle=vehicle,
        expiry_date=date(2099, 12, 31), status=TagStatus.ACTIVE,
    )
    return user, vehicle, account


class DeviceRegistrationTest(TestCase):
    def setUp(self):
        self.user, _, _ = make_holder()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_register_is_idempotent(self):
        for _ in range(2):
            response = self.client.post(
                '/api/v1/notifications/devices/register/',
                {'token': 'tok-abc', 'platform': 'android'},
                format='json',
            )
            self.assertIn(response.status_code, (200, 201))
        self.assertEqual(DeviceToken.objects.filter(token='tok-abc').count(), 1)

    def test_token_moves_to_the_new_owner(self):
        """FCM hands the same token to whoever installs next on a device.

        If the row did not move, the previous owner would keep receiving the new owner's
        balance notifications — someone else's money, on their phone.
        """
        self.client.post(
            '/api/v1/notifications/devices/register/',
            {'token': 'shared-device', 'platform': 'android'},
            format='json',
        )
        other = User.objects.create_user(
            phone='03004445566', password='otherpass123', full_name='Second Owner'
        )
        client = APIClient()
        client.force_authenticate(user=other)
        client.post(
            '/api/v1/notifications/devices/register/',
            {'token': 'shared-device', 'platform': 'android'},
            format='json',
        )

        self.assertEqual(DeviceToken.objects.filter(token='shared-device').count(), 1)
        self.assertEqual(
            DeviceToken.objects.get(token='shared-device').user_id, other.id
        )

    def test_token_is_never_returned(self):
        """The token is a capability — anyone holding it can push to that device."""
        response = self.client.post(
            '/api/v1/notifications/devices/register/',
            {'token': 'secret-token-value', 'platform': 'android'},
            format='json',
        )
        self.assertNotIn('secret-token-value', response.content.decode())

    def test_status_reports_push_unavailable_without_fcm(self):
        """The LAN deployment has no FCM. Saying otherwise would be a lie the app repeats."""
        response = self.client.get('/api/v1/notifications/status/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.json()['data']['push_available'])

    def test_unregister_removes_only_own_device(self):
        self.client.post(
            '/api/v1/notifications/devices/register/',
            {'token': 'mine', 'platform': 'android'},
            format='json',
        )
        other = User.objects.create_user(
            phone='03004445566', password='otherpass123', full_name='Other'
        )
        DeviceToken.objects.create(user=other, token='theirs')

        self.client.post(
            '/api/v1/notifications/devices/unregister/',
            {'token': 'theirs'},
            format='json',
        )
        self.assertTrue(DeviceToken.objects.filter(token='theirs').exists())

    def test_requires_authentication(self):
        response = APIClient().post(
            '/api/v1/notifications/devices/register/',
            {'token': 'x'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(FCM_PROJECT_ID='p', FCM_CREDENTIALS_FILE='/nonexistent.json')
class TransactionNotificationTest(TransactionTestCase):
    """TransactionTestCase, not TestCase: `on_commit` callbacks do not run inside the
    outer atomic block TestCase wraps every test in, so the signals under test would
    never fire."""

    def setUp(self):
        self.user, self.vehicle, self.account = make_holder()
        DeviceToken.objects.create(user=self.user, token='tok', platform='android')

    def _txn(self, txn_type, amount='150.00', **kwargs):
        return Transaction.objects.create(
            account=self.account,
            transaction_type=txn_type,
            amount=Decimal(amount),
            balance_before=Decimal('1000.00'),
            balance_after=Decimal('850.00'),
            status=kwargs.pop('status', TransactionStatus.SUCCESS),
            **kwargs,
        )

    def test_toll_deduction_notifies_with_plate_and_balance(self):
        with patch('apps.notifications.signals.send_to_user') as send:
            self._txn(TransactionType.TOLL_DEDUCTION)
        send.assert_called_once()
        kwargs = send.call_args.kwargs
        self.assertIn('Rs. 150', kwargs['title'])
        self.assertIn('KHI1001', kwargs['body'])
        self.assertIn('Rs. 850', kwargs['body'])

    def test_offline_synced_toll_says_so(self):
        """It can arrive long after the driver left the plaza; without the note it reads as
        a duplicate charge."""
        with patch('apps.notifications.signals.send_to_user') as send:
            self._txn(
                TransactionType.TOLL_DEDUCTION,
                source=TransactionSource.OFFLINE_EXIT_SYNC,
            )
        self.assertIn('synced from booth', send.call_args.kwargs['body'])

    def test_topup_notifies(self):
        with patch('apps.notifications.signals.send_to_user') as send:
            self._txn(TransactionType.TOPUP, amount='1000.00')
        self.assertIn('Top-up received', send.call_args.kwargs['title'])

    def test_refund_notifies(self):
        with patch('apps.notifications.signals.send_to_user') as send:
            self._txn(TransactionType.REFUND)
        self.assertIn('Refund', send.call_args.kwargs['title'])

    def test_pending_and_failed_transactions_are_silent(self):
        with patch('apps.notifications.signals.send_to_user') as send:
            self._txn(TransactionType.TOPUP, status=TransactionStatus.PENDING)
            self._txn(TransactionType.TOLL_DEDUCTION, status=TransactionStatus.FAILED)
        send.assert_not_called()

    def test_nothing_is_sent_for_a_rolled_back_transaction(self):
        """THE invariant. Both CashTopupView and ExitService write the Transaction inside an
        atomic() block that can still fail afterwards. Pushing "you were charged Rs. 150" for
        money that never moved is worse than not pushing at all."""
        with patch('apps.notifications.signals.send_to_user') as send:
            try:
                with db_transaction.atomic():
                    self._txn(TransactionType.TOLL_DEDUCTION)
                    raise RuntimeError('simulated failure after the row was written')
            except RuntimeError:
                pass
        send.assert_not_called()

    def test_a_broken_notification_never_breaks_the_payment(self):
        """The other invariant. A bug in message construction must not turn a successful
        top-up into a 500 — the money has already moved by the time this runs."""
        with patch(
            'apps.notifications.signals.send_to_user',
            side_effect=RuntimeError('FCM exploded'),
        ):
            txn = self._txn(TransactionType.TOPUP, amount='500.00')

        # The row survived and is readable: the exception did not propagate.
        self.assertTrue(Transaction.objects.filter(pk=txn.pk).exists())

    def test_send_is_skipped_entirely_when_fcm_is_unconfigured(self):
        with override_settings(FCM_PROJECT_ID='', FCM_CREDENTIALS_FILE=''):
            from .services import send_to_user

            self.assertEqual(
                send_to_user(self.user.id, title='t', body='b'), 0
            )


@override_settings(FCM_PROJECT_ID='p', FCM_CREDENTIALS_FILE='/nonexistent.json')
class TopupFailureNotificationTest(TransactionTestCase):
    def setUp(self):
        self.user, _, self.account = make_holder()
        DeviceToken.objects.create(user=self.user, token='tok')

    def test_failed_topup_notifies_and_says_no_money_was_taken(self):
        topup = TopupRequest.objects.create(
            account=self.account, user=self.user, amount=Decimal('500.00')
        )
        with patch('apps.notifications.signals.send_to_user') as send:
            topup.status = TopupStatus.FAILED
            topup.save()
        send.assert_called_once()
        self.assertIn('No money was taken', send.call_args.kwargs['body'])

    def test_successful_topup_does_not_double_notify(self):
        """A success already writes a Transaction, which notifies. Pushing here as well
        would tell the user about the same money twice."""
        topup = TopupRequest.objects.create(
            account=self.account, user=self.user, amount=Decimal('500.00')
        )
        with patch('apps.notifications.signals.send_to_user') as send:
            topup.status = TopupStatus.SUCCESS
            topup.save()
        send.assert_not_called()

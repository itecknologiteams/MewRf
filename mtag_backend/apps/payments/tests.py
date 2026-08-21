"""Top-up surface: ownership, the Rs. 100 floor, and the merchant-credential leak."""
from datetime import date
from decimal import Decimal

from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Account
from apps.users.models import User
from apps.vehicles.models import Tag, TagStatus, Vehicle
from .models import TopupRequest, TopupStatus


def make_holder(phone, plate, balance='500.00'):
    user = User.objects.create_user(
        phone=phone, password='holderpass123', full_name=f'Holder {phone}'
    )
    vehicle = Vehicle.objects.create(owner=user, plate_number=plate, vehicle_type='car')
    account = Account.objects.create(
        vehicle=vehicle, user=user, balance=Decimal(balance)
    )
    Tag.objects.create(
        tag_serial=f'SER{plate}', tid=f'TID{plate}', vehicle=vehicle,
        expiry_date=date(2099, 12, 31), status=TagStatus.ACTIVE,
    )
    return user, vehicle, account


class InitiateTopupTest(TestCase):
    def setUp(self):
        self.mine = make_holder('03001112233', 'KDE1836')
        self.theirs = make_holder('03004445566', 'ABC1234')
        self.client = APIClient()
        self.client.force_authenticate(user=self.mine[0])

    def test_creates_a_pending_topup_for_own_account(self):
        response = self.client.post(
            '/api/v1/payments/topup/',
            {'account_id': self.mine[2].id, 'amount': '500.00'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        topup = TopupRequest.objects.get(id=response.json()['data']['topup_id'])
        self.assertEqual(topup.status, TopupStatus.PENDING)
        self.assertEqual(topup.account_id, self.mine[2].id)

    def test_balance_is_not_credited_on_initiate(self):
        self.client.post(
            '/api/v1/payments/topup/',
            {'account_id': self.mine[2].id, 'amount': '500.00'},
            format='json',
        )
        self.mine[2].refresh_from_db()
        self.assertEqual(self.mine[2].balance, Decimal('500.00'))

    def test_cannot_initiate_against_another_holders_account(self):
        response = self.client.post(
            '/api/v1/payments/topup/',
            {'account_id': self.theirs[2].id, 'amount': '500.00'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(TopupRequest.objects.filter(account=self.theirs[2]).exists())

    def test_below_minimum_is_rejected(self):
        response = self.client.post(
            '/api/v1/payments/topup/',
            {'account_id': self.mine[2].id, 'amount': '99.00'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('amount', response.json()['errors'])

    def test_exactly_the_minimum_is_accepted(self):
        response = self.client.post(
            '/api/v1/payments/topup/',
            {'account_id': self.mine[2].id, 'amount': '100.00'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @override_settings(
        JAZZCASH_MERCHANT_ID='MC00001',
        JAZZCASH_PASSWORD='super-secret-merchant-password',
        JAZZCASH_INTEGRITY_SALT='salt',
        JAZZCASH_RETURN_URL='https://example.test/return',
    )
    def test_response_never_carries_the_merchant_password(self):
        """This payload goes to a mobile app on a stranger's phone. Anyone who
        installed it could read pp_Password out of the response body and transact
        as the merchant."""
        response = self.client.post(
            '/api/v1/payments/topup/',
            {'account_id': self.mine[2].id, 'amount': '500.00'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payload = response.json()['data']['jazzcash_payload']
        self.assertNotIn('pp_Password', payload)
        self.assertNotIn(
            'super-secret-merchant-password', response.content.decode()
        )
        # The fields the client legitimately needs are still there.
        self.assertEqual(payload['pp_MerchantID'], 'MC00001')
        self.assertEqual(payload['pp_Amount'], '50000')
        self.assertEqual(payload['pp_TxnCurrency'], 'PKR')
        self.assertIn('pp_SecureHash', payload)


class TopupHistoryOwnershipTest(TestCase):
    def setUp(self):
        self.mine = make_holder('03001112233', 'KDE1836')
        self.theirs = make_holder('03004445566', 'ABC1234')
        TopupRequest.objects.create(
            account=self.mine[2], user=self.mine[0], amount=Decimal('500.00')
        )
        TopupRequest.objects.create(
            account=self.theirs[2], user=self.theirs[0], amount=Decimal('7777.00')
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.mine[0])

    def test_own_history_readable(self):
        response = self.client.get(f'/api/v1/payments/history/{self.mine[2].id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.json()['data']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['amount'], '500.00')
        self.assertEqual(rows[0]['status'], TopupStatus.PENDING)

    def test_another_holders_history_is_404(self):
        response = self.client.get(f'/api/v1/payments/history/{self.theirs[2].id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertNotIn('7777.00', response.content.decode())

"""Consumer-scoped account surface: ownership isolation and the dashboard summary.

Every test here exists because the endpoint it covers used to be reachable for
any authenticated caller with any id in the path. A regression would not raise —
it would quietly serve one motorist another motorist's balance — so these assert
on 404, not merely on the happy path.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import (
    Account, Transaction, TransactionSource, TransactionStatus, TransactionType,
)
from apps.users.models import User, UserRole
from apps.vehicles.models import Tag, TagStatus, Vehicle
from utils.dates import add_months


def make_holder(phone, plate, balance='500.00', with_tag=True, tid=None):
    """A consumer with one vehicle, one wallet and (usually) one tag."""
    user = User.objects.create_user(
        phone=phone, password='holderpass123', full_name=f'Holder {phone}'
    )
    vehicle = Vehicle.objects.create(owner=user, plate_number=plate, vehicle_type='car')
    account = Account.objects.create(
        vehicle=vehicle, user=user, balance=Decimal(balance)
    )
    tag = None
    if with_tag:
        tag = Tag.objects.create(
            tag_serial=f'SER{plate}', tid=tid or f'TID{plate}', epc=f'EPC{plate}',
            vehicle=vehicle, expiry_date=date(2099, 12, 31), status=TagStatus.ACTIVE,
        )
    return user, vehicle, account, tag


def add_txn(account, amount, txn_type=TransactionType.TOLL_DEDUCTION, source=None):
    before = account.balance
    after = before - Decimal(amount) if txn_type == TransactionType.TOLL_DEDUCTION \
        else before + Decimal(amount)
    return Transaction.objects.create(
        account=account, transaction_type=txn_type, amount=Decimal(amount),
        balance_before=before, balance_after=after,
        status=TransactionStatus.SUCCESS, source=source,
    )


class AccountOwnershipTest(TestCase):
    def setUp(self):
        self.mine = make_holder('03001112233', 'KDE1836')
        self.theirs = make_holder('03004445566', 'ABC1234', balance='9999.00')
        self.client = APIClient()
        self.client.force_authenticate(user=self.mine[0])

    def test_can_read_own_balance(self):
        response = self.client.get(f'/api/v1/accounts/vehicle/{self.mine[1].id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['data']
        self.assertEqual(data['balance'], '500.00')
        self.assertEqual(data['plate_number'], 'KDE1836')
        self.assertEqual(data['id'], self.mine[2].id)
        self.assertEqual(data['vehicle_id'], self.mine[1].id)

    def test_another_holders_balance_is_404_not_403(self):
        """404, so the response cannot be used to confirm the id exists."""
        response = self.client.get(f'/api/v1/accounts/vehicle/{self.theirs[1].id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertNotIn('9999.00', response.content.decode())

    def test_another_holders_transactions_are_404(self):
        add_txn(self.theirs[2], '250.00')
        response = self.client.get(
            f'/api/v1/accounts/{self.theirs[2].id}/transactions/'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_operator_keeps_cross_account_access(self):
        operator = User.objects.create_user(
            phone='03007776655', password='oppass123456', full_name='Operator',
            user_role=UserRole.OPERATOR,
        )
        client = APIClient()
        client.force_authenticate(user=operator)
        response = client.get(f'/api/v1/accounts/vehicle/{self.theirs[1].id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class TransactionSerializerFieldsTest(TestCase):
    def setUp(self):
        self.mine = make_holder('03001112233', 'KDE1836')
        self.client = APIClient()
        self.client.force_authenticate(user=self.mine[0])

    def test_source_is_exposed(self):
        """The app shows a 'synced from booth' note for offline_exit_sync, so it
        needs `source`; the serializer used to omit it entirely."""
        add_txn(self.mine[2], '120.00', source=TransactionSource.OFFLINE_EXIT_SYNC)
        response = self.client.get(f'/api/v1/accounts/{self.mine[2].id}/transactions/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = response.json()['data'][0]
        self.assertEqual(row['source'], TransactionSource.OFFLINE_EXIT_SYNC)

    def test_type_filter(self):
        add_txn(self.mine[2], '120.00')
        add_txn(self.mine[2], '1000.00', txn_type=TransactionType.TOPUP)
        response = self.client.get(
            f'/api/v1/accounts/{self.mine[2].id}/transactions/?type=topup'
        )
        rows = response.json()['data']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['transaction_type'], TransactionType.TOPUP)

    def test_money_is_serialised_as_a_string(self):
        add_txn(self.mine[2], '120.50')
        row = self.client.get(
            f'/api/v1/accounts/{self.mine[2].id}/transactions/'
        ).json()['data'][0]
        self.assertIsInstance(row['amount'], str)
        self.assertEqual(row['amount'], '120.50')


class MyAccountSummaryTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone='03001112233', password='holderpass123', full_name='Three Car Holder'
        )
        self.vehicles = []
        for i, plate in enumerate(['KDE1836', 'KDE1837', 'KDE1838']):
            vehicle = Vehicle.objects.create(
                owner=self.user, plate_number=plate, vehicle_type='car'
            )
            account = Account.objects.create(
                vehicle=vehicle, user=self.user, balance=Decimal('100.00') * (i + 1)
            )
            # The third vehicle has no tag — a reissue in progress.
            if i < 2:
                Tag.objects.create(
                    tag_serial=f'SER{plate}', tid=f'TID{plate}', vehicle=vehicle,
                    expiry_date=date(2099, 12, 31), status=TagStatus.ACTIVE,
                )
            self.vehicles.append((vehicle, account))

        self.other = make_holder('03004445566', 'ABC1234', balance='9999.00')

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_summary_counts_and_total(self):
        response = self.client.get('/api/v1/accounts/my/summary/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['data']
        self.assertEqual(data['total_balance'], '600.00')
        self.assertEqual(data['account_count'], 3)
        self.assertEqual(data['vehicle_count'], 3)
        self.assertEqual(data['tag_count'], 2)
        self.assertEqual(len(data['accounts']), 3)

    def test_summary_excludes_other_holders(self):
        add_txn(self.other[2], '777.00')
        data = self.client.get('/api/v1/accounts/my/summary/').json()['data']
        plates = {a['plate_number'] for a in data['accounts']}
        self.assertNotIn('ABC1234', plates)
        self.assertNotIn('777.00', response_amounts(data))

    def test_month_to_date_tolls(self):
        add_txn(self.vehicles[0][1], '60.00')
        add_txn(self.vehicles[1][1], '90.00')
        # A top-up must not be counted as a toll.
        add_txn(self.vehicles[0][1], '1000.00', txn_type=TransactionType.TOPUP)
        # A deduction from before this month must not be counted either.
        old = add_txn(self.vehicles[0][1], '500.00')
        Transaction.objects.filter(pk=old.pk).update(
            processed_at=timezone.localtime().replace(day=1) - timedelta(days=2)
        )

        data = self.client.get('/api/v1/accounts/my/summary/').json()['data']
        self.assertEqual(data['month_toll_total'], '150.00')
        self.assertEqual(data['month_toll_count'], 2)

    def test_recent_transactions_are_merged_newest_first_and_labelled(self):
        add_txn(self.vehicles[0][1], '60.00')
        add_txn(self.vehicles[1][1], '90.00')
        data = self.client.get('/api/v1/accounts/my/summary/').json()['data']
        recent = data['recent_transactions']
        self.assertEqual(len(recent), 2)
        self.assertEqual(recent[0]['plate_number'], 'KDE1837')
        self.assertEqual(recent[0]['account_id'], self.vehicles[1][1].id)
        self.assertIn('plate_number', recent[0])

    def test_requires_authentication(self):
        client = APIClient()
        response = client.get('/api/v1/accounts/my/summary/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


def response_amounts(data):
    return [t['amount'] for t in data['recent_transactions']]


class CashTopupIssuanceTest(TestCase):
    """Registration at the booth: the service charge, the tag's term, and the
    vehicle class the operator picked.

    The wallet used to be opened with the whole cash amount, every tag was
    written with a 2099 expiry, and every vehicle was filed as a car — so the
    till never balanced against the wallets, an expired tag looked valid
    forever, and a truck was billed at the car fare. Each test here pins one of
    those three down.
    """

    def setUp(self):
        self.client = APIClient()
        self.operator = User.objects.create_user(
            phone='03009998877', password='operatorpass123', full_name='Booth Op',
            user_role=UserRole.OPERATOR,
        )
        self.client.force_authenticate(user=self.operator)

    def _register(self, **over):
        payload = {
            'tid': 'TIDNEW01', 'amount': '1000', 'consumer_name': 'Ali Raza',
            'phone': '03001112222', 'vehicle_reg': 'ABC-123',
        }
        payload.update(over)
        return self.client.post('/api/v1/accounts/topup/cash/', payload, format='json')

    def test_service_charge_comes_out_of_the_cash_handed_over(self):
        resp = self._register()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        data = resp.json()['data']
        self.assertEqual(data['amount_collected'], '1000.00')
        self.assertEqual(data['service_charge'], '350.00')
        self.assertEqual(data['new_balance'], '650.00')

        account = Account.objects.get(vehicle__plate_number='ABC123')
        self.assertEqual(account.balance, Decimal('650.00'))
        txn = Transaction.objects.get(account=account)
        # `amount` is what the wallet moved; the fee is recorded beside it, so
        # cash collected is recoverable as amount + service_charge.
        self.assertEqual(txn.amount, Decimal('650.00'))
        self.assertEqual(txn.service_charge, Decimal('350.00'))

    def test_operator_can_override_the_charge(self):
        resp = self._register(service_charge='0')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        data = resp.json()['data']
        self.assertEqual(data['service_charge'], '0.00')
        self.assertEqual(data['new_balance'], '1000.00')
        self.assertEqual(
            Transaction.objects.get().service_charge, Decimal('0.00')
        )

    def test_amount_below_the_charge_is_rejected(self):
        resp = self._register(amount='200')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('service charge', resp.json()['message'])
        # Nothing half-written: no user, vehicle or wallet from a failed attempt.
        self.assertFalse(Vehicle.objects.filter(plate_number='ABC123').exists())
        self.assertFalse(User.objects.filter(phone='03001112222').exists())

    def test_negative_charge_is_rejected(self):
        resp = self._register(service_charge='-50')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_repeat_topup_on_an_issued_tag_is_not_charged(self):
        self._register()
        tag = Tag.objects.get(tid='TIDNEW01')
        resp = self.client.post(
            '/api/v1/accounts/topup/cash/',
            {'tid': 'TIDNEW01', 'amount': '500'}, format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()['data']
        self.assertEqual(data['service_charge'], '0.00')
        self.assertEqual(data['new_balance'], '1150.00')  # 650 + 500, no fee
        topup = Transaction.objects.filter(account__vehicle=tag.vehicle).latest('processed_at')
        self.assertEqual(topup.service_charge, Decimal('0.00'))

    def test_tag_expires_two_years_after_issue(self):
        resp = self._register()
        expected = add_months(timezone.localdate(), 24)
        self.assertEqual(resp.json()['data']['expiry_date'], expected.isoformat())
        self.assertEqual(Tag.objects.get(tid='TIDNEW01').expiry_date, expected)

    def test_expiry_is_reset_when_a_stocked_tag_is_issued(self):
        # A tag row that has sat in stock since before today still gets a full
        # term from the day it is actually handed over.
        Tag.objects.create(
            tag_serial='STOCK01', tid='TIDNEW01', epc='EPC01',
            expiry_date=date(2020, 1, 1), status=TagStatus.DEACTIVATED,
        )
        self._register()
        self.assertEqual(
            Tag.objects.get(tid='TIDNEW01').expiry_date,
            add_months(timezone.localdate(), 24),
        )

    def test_vehicle_is_registered_under_the_selected_category(self):
        resp = self._register(vehicle_type='truck_2axle')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.json()['data']['vehicle_type'], 'truck_2axle')
        self.assertEqual(
            Vehicle.objects.get(plate_number='ABC123').vehicle_type, 'truck_2axle'
        )

    def test_unknown_category_is_rejected_not_silently_filed_as_a_car(self):
        resp = self._register(vehicle_type='spaceship')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Vehicle.objects.filter(plate_number='ABC123').exists())

    def test_category_defaults_to_car_for_clients_that_do_not_send_one(self):
        self._register()
        self.assertEqual(
            Vehicle.objects.get(plate_number='ABC123').vehicle_type, 'car'
        )

    def test_lookup_quotes_the_charge_and_term_for_an_unissued_tag(self):
        resp = self.client.post(
            '/api/v1/accounts/topup/lookup/', {'tid': 'TIDNEW01'}, format='json',
        )
        data = resp.json()['data']
        self.assertFalse(data['found'])
        self.assertEqual(data['service_charge'], '350.00')
        self.assertEqual(data['validity_months'], 24)
        self.assertEqual(
            data['expiry_date'], add_months(timezone.localdate(), 24).isoformat()
        )

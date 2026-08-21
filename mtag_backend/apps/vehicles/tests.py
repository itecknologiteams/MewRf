"""Consumer-scoped vehicle and tag surface for the M-Tag User App."""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Account
from apps.users.models import User, UserRole
from .models import Tag, TagStatus, Vehicle


class MyVehiclesTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone='03001112233', password='holderpass123', full_name='Tag Holder'
        )
        self.with_tag = Vehicle.objects.create(
            owner=self.user, plate_number='KDE1836', vehicle_type='truck_2axle'
        )
        self.account = Account.objects.create(
            vehicle=self.with_tag, user=self.user, balance=Decimal('1250.00')
        )
        self.tag = Tag.objects.create(
            tag_serial='SER0001', tid='E28011700000021234ABCD', epc='EPC0001',
            vehicle=self.with_tag, expiry_date=date(2099, 12, 31),
            status=TagStatus.ACTIVE,
        )
        # A vehicle mid-reissue: no tag row at all.
        self.no_tag = Vehicle.objects.create(
            owner=self.user, plate_number='KDE1837', vehicle_type='car'
        )
        Account.objects.create(
            vehicle=self.no_tag, user=self.user, balance=Decimal('40.00')
        )

        self.stranger = User.objects.create_user(
            phone='03004445566', password='otherpass123', full_name='Someone Else'
        )
        self.their_vehicle = Vehicle.objects.create(
            owner=self.stranger, plate_number='ABC1234', vehicle_type='car'
        )
        Account.objects.create(
            vehicle=self.their_vehicle, user=self.stranger, balance=Decimal('9999.00')
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_lists_only_my_vehicles(self):
        response = self.client.get('/api/v1/vehicles/my/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        plates = {v['plate_number'] for v in response.json()['data']}
        self.assertEqual(plates, {'KDE1836', 'KDE1837'})

    def test_carries_tag_account_id_and_balance(self):
        rows = {v['plate_number']: v for v in
                self.client.get('/api/v1/vehicles/my/').json()['data']}
        mine = rows['KDE1836']
        self.assertEqual(mine['account_id'], self.account.id)
        self.assertEqual(mine['balance'], '1250.00')
        self.assertEqual(mine['vehicle_type'], 'truck_2axle')
        self.assertEqual(mine['tag']['tag_serial'], 'SER0001')
        self.assertTrue(mine['tag']['is_valid'])

    def test_tid_is_exposed(self):
        """The JazzCash aggregator flow is keyed on the chip TID — the app cannot
        tell a holder how to top up without it."""
        rows = {v['plate_number']: v for v in
                self.client.get('/api/v1/vehicles/my/').json()['data']}
        self.assertEqual(rows['KDE1836']['tag']['tid'], 'E28011700000021234ABCD')
        self.assertEqual(rows['KDE1836']['tag']['epc'], 'EPC0001')

    def test_vehicle_without_a_tag_is_returned_with_tag_null(self):
        rows = {v['plate_number']: v for v in
                self.client.get('/api/v1/vehicles/my/').json()['data']}
        self.assertIsNone(rows['KDE1837']['tag'])
        self.assertEqual(rows['KDE1837']['balance'], '40.00')

    def test_vehicle_without_an_account_reports_null_not_zero(self):
        """Rs. 0 and 'we do not know' are different facts; the app must not show
        a balance it was never told."""
        Vehicle.objects.create(
            owner=self.user, plate_number='KDE1839', vehicle_type='car'
        )
        rows = {v['plate_number']: v for v in
                self.client.get('/api/v1/vehicles/my/').json()['data']}
        self.assertIsNone(rows['KDE1839']['balance'])
        self.assertIsNone(rows['KDE1839']['account_id'])

    def test_requires_authentication(self):
        response = APIClient().get('/api/v1/vehicles/my/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_tag_is_read_only_no_write_path(self):
        """`my/` is a GET-only surface — no tag issuance from the consumer app."""
        response = self.client.post('/api/v1/vehicles/my/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class VehicleDetailOwnershipTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone='03001112233', password='holderpass123', full_name='Tag Holder'
        )
        self.mine = Vehicle.objects.create(
            owner=self.user, plate_number='KDE1836', vehicle_type='car'
        )
        self.stranger = User.objects.create_user(
            phone='03004445566', password='otherpass123', full_name='Someone Else'
        )
        self.theirs = Vehicle.objects.create(
            owner=self.stranger, plate_number='ABC1234', vehicle_type='truck_4axle'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_own_vehicle_readable(self):
        response = self.client.get(f'/api/v1/vehicles/{self.mine.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_other_vehicle_is_404(self):
        response = self.client.get(f'/api/v1/vehicles/{self.theirs.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_other_vehicle_by_plate_is_404(self):
        response = self.client.get('/api/v1/vehicles/plate/ABC-1234/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_own_vehicle_by_plate_normalises(self):
        response = self.client.get('/api/v1/vehicles/plate/kde-1836/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['data']['plate_number'], 'KDE1836')

    def test_consumer_cannot_patch_own_vehicle_type(self):
        """vehicle_type IS the fare class. A holder who could re-declare a 4-axle
        truck as a car would pay car fares — a revenue hole, not a data one."""
        response = self.client.patch(
            f'/api/v1/vehicles/{self.mine.id}/',
            {'vehicle_type': 'motorcycle'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.mine.refresh_from_db()
        self.assertEqual(self.mine.vehicle_type, 'car')

    def test_consumer_cannot_patch_another_vehicle(self):
        response = self.client.patch(
            f'/api/v1/vehicles/{self.theirs.id}/',
            {'vehicle_type': 'car'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.theirs.refresh_from_db()
        self.assertEqual(self.theirs.vehicle_type, 'truck_4axle')

    def test_operator_can_still_patch(self):
        operator = User.objects.create_user(
            phone='03007776655', password='oppass123456', full_name='Operator',
            user_role=UserRole.OPERATOR,
        )
        client = APIClient()
        client.force_authenticate(user=operator)
        response = client.patch(
            f'/api/v1/vehicles/{self.mine.id}/', {'vehicle_type': 'wagon'}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.mine.refresh_from_db()
        self.assertEqual(self.mine.vehicle_type, 'wagon')

    def test_consumer_cannot_reach_the_operator_vehicle_list(self):
        response = self.client.get('/api/v1/vehicles/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

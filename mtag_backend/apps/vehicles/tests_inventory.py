import csv
import io
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from .models import UnregisteredInventory, UnregisteredInventoryStatus, TagActivation, Tag
from apps.accounts.models import Account
from apps.users.models import UserRole

User = get_user_model()


class InventoryUploadAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            phone='03001234567', password='testpass123', full_name='Admin', user_role=UserRole.ADMIN, is_staff=True
        )
        self.client.force_authenticate(user=self.admin_user)

    def test_inventory_upload_csv(self):
        csv_content = """tag_serial,tid,epc,vehicle_plate,vehicle_type,vehicle_color
SER001,TID001,EPC001,LHR1234,car,white
SER002,TID002,EPC002,LHR5678,truck,blue
SER003,TID003,EPC003,LHR9012,bus,red"""

        file = io.StringIO(csv_content)
        file.name = 'inventory.csv'

        response = self.client.post(
            '/api/v1/vehicles/inventory/upload/',
            {'file': file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()['data']
        self.assertEqual(data['added'], 3)
        self.assertEqual(data['skipped'], 0)

        inv = UnregisteredInventory.objects.get(tag_serial='SER001')
        self.assertEqual(inv.status, UnregisteredInventoryStatus.UNREGISTERED)
        self.assertEqual(inv.vehicle_plate, 'LHR1234')

    def test_inventory_upload_duplicates(self):
        UnregisteredInventory.objects.create(
            tag_serial='SER001',
            tid='TID001',
            vehicle_type='car'
        )

        csv_content = """tag_serial,tid,epc,vehicle_plate,vehicle_type,vehicle_color
SER001,TID001,EPC001,LHR1234,car,white
SER002,TID002,EPC002,LHR5678,truck,blue"""

        file = io.StringIO(csv_content)
        file.name = 'inventory.csv'

        response = self.client.post(
            '/api/v1/vehicles/inventory/upload/',
            {'file': file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()['data']
        self.assertEqual(data['added'], 1)
        self.assertEqual(data['skipped'], 1)


class InventoryListAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.operator_user = User.objects.create_user(
            phone='03001234567', password='testpass123', full_name='Operator', user_role=UserRole.OPERATOR
        )
        self.client.force_authenticate(user=self.operator_user)

        UnregisteredInventory.objects.create(
            tag_serial='SER001', tid='TID001', status=UnregisteredInventoryStatus.UNREGISTERED
        )
        UnregisteredInventory.objects.create(
            tag_serial='SER002', tid='TID002', status=UnregisteredInventoryStatus.BOOTH_ASSIGNED,
            booth_assigned_id=1
        )
        UnregisteredInventory.objects.create(
            tag_serial='SER003', tid='TID003', status=UnregisteredInventoryStatus.ACTIVATED,
            first_activated_booth_id=2
        )

    def test_list_all_inventory(self):
        response = self.client.get('/api/v1/vehicles/inventory/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['data']
        self.assertEqual(data['total'], 3)
        self.assertEqual(len(data['items']), 3)

    def test_filter_by_status(self):
        response = self.client.get('/api/v1/vehicles/inventory/?status=unregistered')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['data']
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['items'][0]['tag_serial'], 'SER001')

    def test_filter_by_booth(self):
        response = self.client.get('/api/v1/vehicles/inventory/?booth_assigned_id=1')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['data']
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['items'][0]['booth_assigned_id'], 1)

    def test_search_by_tag_serial(self):
        response = self.client.get('/api/v1/vehicles/inventory/?search=SER002')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['data']
        self.assertEqual(data['total'], 1)


class BoothAssignmentAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            phone='03001234567', password='testpass123', full_name='Admin', user_role=UserRole.ADMIN, is_staff=True
        )
        self.client.force_authenticate(user=self.admin_user)

        self.inv1 = UnregisteredInventory.objects.create(
            tag_serial='SER001', tid='TID001', status=UnregisteredInventoryStatus.UNREGISTERED
        )
        self.inv2 = UnregisteredInventory.objects.create(
            tag_serial='SER002', tid='TID002', status=UnregisteredInventoryStatus.UNREGISTERED
        )

    def test_assign_to_booth(self):
        response = self.client.post(
            '/api/v1/vehicles/inventory/assign-booth/',
            {
                'inventory_ids': [str(self.inv1.id), str(self.inv2.id)],
                'booth_id': 3,
                'assigned_by': 'admin@test.com'
            },
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['data']
        self.assertEqual(data['assigned'], 2)

        self.inv1.refresh_from_db()
        self.assertEqual(self.inv1.booth_assigned_id, 3)
        self.assertEqual(self.inv1.status, UnregisteredInventoryStatus.BOOTH_ASSIGNED)


class InventoryCheckAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.operator_user = User.objects.create_user(
            phone='03001234567', password='testpass123', full_name='Operator', user_role=UserRole.OPERATOR
        )
        self.client.force_authenticate(user=self.operator_user)

        self.inv_unregistered = UnregisteredInventory.objects.create(
            tag_serial='SER001', tid='TID001', status=UnregisteredInventoryStatus.UNREGISTERED
        )
        self.inv_assigned = UnregisteredInventory.objects.create(
            tag_serial='SER002', tid='TID002', status=UnregisteredInventoryStatus.BOOTH_ASSIGNED,
            booth_assigned_id=2
        )
        self.inv_activated = UnregisteredInventory.objects.create(
            tag_serial='SER003', tid='TID003', status=UnregisteredInventoryStatus.ACTIVATED,
            first_activated_booth_id=3
        )

    def test_check_unregistered_tag(self):
        response = self.client.get('/api/v1/vehicles/inventory/check/SER001/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['data']
        self.assertTrue(data['found'])
        self.assertEqual(data['status'], 'unregistered')
        self.assertFalse(data['can_activate'])

    def test_check_booth_assigned_tag(self):
        response = self.client.get('/api/v1/vehicles/inventory/check/SER002/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['data']
        self.assertTrue(data['found'])
        self.assertEqual(data['status'], 'booth_assigned')
        self.assertEqual(data['booth_assigned_id'], 2)
        self.assertTrue(data['can_activate'])

    def test_check_activated_tag(self):
        response = self.client.get('/api/v1/vehicles/inventory/check/SER003/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['data']
        self.assertTrue(data['found'])
        self.assertEqual(data['status'], 'activated')
        self.assertEqual(data['first_activated_booth_id'], 3)
        self.assertFalse(data['activation_required'])

    def test_check_nonexistent_tag(self):
        response = self.client.get('/api/v1/vehicles/inventory/check/NONEXISTENT/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['data']
        self.assertFalse(data['found'])
        self.assertEqual(data['status'], 'not_in_inventory')


class TagActivationAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.operator_user = User.objects.create_user(
            phone='03001234567', password='testpass123', full_name='Operator', user_role=UserRole.OPERATOR
        )
        self.client.force_authenticate(user=self.operator_user)

        self.inv = UnregisteredInventory.objects.create(
            tag_serial='SER001',
            tid='TID001',
            status=UnregisteredInventoryStatus.BOOTH_ASSIGNED,
            booth_assigned_id=2
        )

    def test_activate_quick_create(self):
        response = self.client.post(
            '/api/v1/vehicles/inventory/activate/',
            {
                'tag_serial': 'SER001',
                'tid': 'TID001',
                'customer_name': 'John Doe',
                'customer_phone': '03001234567',
                'initial_topup': 1000,
                'payment_method': 'CASH',
                'activation_booth_id': 2
            },
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()['data']
        self.assertEqual(data['status'], UnregisteredInventoryStatus.ACTIVATED)
        self.assertEqual(data['first_activated_booth_id'], 2)

        self.inv.refresh_from_db()
        self.assertIsNotNone(self.inv.activated_for_account)

    def test_activate_link_existing(self):
        from .models import Vehicle
        user = User.objects.create_user(
            phone='03009876543', password='testpass123', full_name='Customer', user_role=UserRole.USER
        )
        vehicle = Vehicle.objects.create(
            owner=user,
            plate_number='TEST1234',
            vehicle_type='car',
        )
        account = Account.objects.create(user=user, vehicle=vehicle, balance=500)

        response = self.client.post(
            '/api/v1/vehicles/inventory/activate-existing/',
            {
                'tag_serial': 'SER001',
                'tid': 'TID001',
                'account_id': str(account.id),
                'activation_booth_id': 2
            },
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['data']
        self.assertEqual(data['status'], UnregisteredInventoryStatus.ACTIVATED)

        self.inv.refresh_from_db()
        self.assertEqual(self.inv.activated_for_account_id, account.id)


class BoothTopupActivationTest(TestCase):
    """Booth-aware cash topup: register + activate an inventory tag at a booth."""

    def setUp(self):
        self.client = APIClient()
        self.operator = User.objects.create_user(
            phone='03001234567', password='testpass123', full_name='Op',
            user_role=UserRole.OPERATOR,
        )
        self.client.force_authenticate(user=self.operator)
        self.inv = UnregisteredInventory.objects.create(
            tag_serial='SER900', tid='TID900', vehicle_type='car',
            status=UnregisteredInventoryStatus.BOOTH_ASSIGNED, booth_assigned_id=2,
        )

    def _payload(self, **over):
        base = {
            'tid': 'TID900', 'amount': '500', 'consumer_name': 'Ali',
            'phone': '03007778888', 'vehicle_reg': 'LEB1234', 'activation_booth_id': 2,
        }
        base.update(over)
        return base

    def test_booth_mismatch_rejected(self):
        resp = self.client.post('/api/v1/accounts/topup/cash/',
                                self._payload(activation_booth_id=5), format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Booth 2', resp.json()['message'])
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.status, UnregisteredInventoryStatus.BOOTH_ASSIGNED)

    def test_activation_success_marks_inventory_and_audit(self):
        resp = self.client.post('/api/v1/accounts/topup/cash/',
                                self._payload(), format='json')
        self.assertEqual(resp.status_code, 201)
        data = resp.json()['data']
        self.assertTrue(data['registered'])
        self.assertIn('receipt', data)
        self.assertEqual(data['receipt']['vehicle_reg'], 'LEB1234')
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.status, UnregisteredInventoryStatus.ACTIVATED)
        self.assertEqual(self.inv.first_activated_booth_id, 2)
        self.assertTrue(TagActivation.objects.filter(
            tag_serial='SER900', first_scan_booth_id=2).exists())
        # Tag row created with the inventory's printed serial (not a generated one)
        self.assertTrue(Tag.objects.filter(tag_serial='SER900', tid='TID900').exists())

    def test_already_activated_rejected(self):
        self.inv.status = UnregisteredInventoryStatus.ACTIVATED
        self.inv.save(update_fields=['status'])
        resp = self.client.post('/api/v1/accounts/topup/cash/',
                                self._payload(), format='json')
        self.assertEqual(resp.status_code, 400)

    def test_no_booth_id_preserves_flutter_behavior(self):
        # No activation_booth_id and a TID not in inventory → plain register, untouched inventory
        resp = self.client.post('/api/v1/accounts/topup/cash/',
                                self._payload(tid='TID901', vehicle_reg='LEB9999',
                                              activation_booth_id=None), format='json')
        self.assertEqual(resp.status_code, 201)
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.status, UnregisteredInventoryStatus.BOOTH_ASSIGNED)

    def test_lookup_reports_inventory_status(self):
        resp = self.client.post('/api/v1/accounts/topup/lookup/',
                                {'tid': 'TID900'}, format='json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertFalse(data['found'])
        self.assertEqual(data['inventory_status'], 'booth_assigned')
        self.assertEqual(data['booth_assigned_id'], 2)

"""Admin lane CRUD — the endpoints behind the Lane Management view."""

from django.test import TestCase
from rest_framework.test import APIClient

from apps.tolls.models import Plaza, TollLane
from apps.users.models import User, UserRole


class AdminLaneApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            phone='03001234567', password='testpass123', full_name='Admin',
            user_role=UserRole.ADMIN, is_staff=True,
        )
        self.client.force_authenticate(user=self.admin)
        self.plaza = Plaza.objects.create(plaza_id=1, name='Test Plaza')

    def test_list_lanes_for_plaza(self):
        TollLane.objects.create(plaza=self.plaza, lane_number=2)
        TollLane.objects.create(plaza=self.plaza, lane_number=1)
        res = self.client.get(f'/api/v1/tolls/admin/plazas/{self.plaza.id}/lanes/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual([l['lane_number'] for l in res.json()['data']], [1, 2])

    def test_create_lane(self):
        res = self.client.post(
            f'/api/v1/tolls/admin/plazas/{self.plaza.id}/lanes/',
            {'lane_number': 3, 'is_active': True}, format='json',
        )
        self.assertEqual(res.status_code, 201)
        self.assertTrue(TollLane.objects.filter(plaza=self.plaza, lane_number=3).exists())

    def test_create_rejects_lane_number_below_one(self):
        res = self.client.post(
            f'/api/v1/tolls/admin/plazas/{self.plaza.id}/lanes/',
            {'lane_number': 0}, format='json',
        )
        self.assertEqual(res.status_code, 400)
        self.assertFalse(TollLane.objects.filter(plaza=self.plaza).exists())

    def test_create_duplicate_lane_number_is_rejected(self):
        TollLane.objects.create(plaza=self.plaza, lane_number=1)
        res = self.client.post(
            f'/api/v1/tolls/admin/plazas/{self.plaza.id}/lanes/',
            {'lane_number': 1}, format='json',
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(TollLane.objects.filter(plaza=self.plaza).count(), 1)

    def test_patch_renumbers_and_deactivates(self):
        lane = TollLane.objects.create(plaza=self.plaza, lane_number=1)
        res = self.client.patch(
            f'/api/v1/tolls/admin/lanes/{lane.id}/',
            {'lane_number': 9, 'is_active': False}, format='json',
        )
        self.assertEqual(res.status_code, 200)
        lane.refresh_from_db()
        self.assertEqual(lane.lane_number, 9)
        self.assertFalse(lane.is_active)

    def test_patch_to_taken_lane_number_is_rejected(self):
        TollLane.objects.create(plaza=self.plaza, lane_number=1)
        lane = TollLane.objects.create(plaza=self.plaza, lane_number=2)
        res = self.client.patch(
            f'/api/v1/tolls/admin/lanes/{lane.id}/', {'lane_number': 1}, format='json',
        )
        self.assertEqual(res.status_code, 400)
        lane.refresh_from_db()
        self.assertEqual(lane.lane_number, 2)

    def test_delete_unused_lane(self):
        lane = TollLane.objects.create(plaza=self.plaza, lane_number=1)
        res = self.client.delete(f'/api/v1/tolls/admin/lanes/{lane.id}/')
        self.assertEqual(res.status_code, 200)
        self.assertFalse(TollLane.objects.filter(pk=lane.id).exists())

    def test_delete_lane_with_traffic_is_refused(self):
        """Trip FKs are SET_NULL, so a delete would silently orphan history."""
        from apps.accounts.models import Account
        from apps.vehicles.models import Vehicle, Tag, VehicleType
        from apps.tolls.models import TollTrip

        lane = TollLane.objects.create(plaza=self.plaza, lane_number=1)
        vehicle = Vehicle.objects.create(
            plate_number='ABC123', vehicle_type=VehicleType.CAR, owner=self.admin,
        )
        account = Account.objects.create(vehicle=vehicle, user=self.admin, balance=1000)
        tag = Tag.objects.create(tag_serial='TAG0001', vehicle=vehicle)
        TollTrip.objects.create(
            vehicle=vehicle, tag=tag, account=account,
            entry_plaza=self.plaza, entry_lane=lane,
        )

        res = self.client.delete(f'/api/v1/tolls/admin/lanes/{lane.id}/')
        self.assertEqual(res.status_code, 409)
        self.assertTrue(TollLane.objects.filter(pk=lane.id).exists())

    def test_non_admin_cannot_manage_lanes(self):
        lane = TollLane.objects.create(plaza=self.plaza, lane_number=1)
        operator = User.objects.create_user(
            phone='03009999999', password='testpass123', full_name='Op',
            user_role=UserRole.OPERATOR,
        )
        self.client.force_authenticate(user=operator)
        self.assertEqual(
            self.client.patch(f'/api/v1/tolls/admin/lanes/{lane.id}/',
                              {'is_active': False}, format='json').status_code, 403,
        )
        self.assertEqual(
            self.client.delete(f'/api/v1/tolls/admin/lanes/{lane.id}/').status_code, 403,
        )

    def test_missing_lane_returns_404(self):
        self.assertEqual(
            self.client.patch('/api/v1/tolls/admin/lanes/99999/',
                              {'is_active': False}, format='json').status_code, 404,
        )
        self.assertEqual(
            self.client.delete('/api/v1/tolls/admin/lanes/99999/').status_code, 404,
        )

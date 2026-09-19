"""Identifying a physically-scanned tag at the registration desk.

The operator has a tag in their hand and no idea which row it is. A reader gives
a TID, never the printed serial, so this is the only call that can answer "can I
give this one to the customer in front of me?".
"""

from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Account
from apps.users.models import User, UserRole
from apps.vehicles.models import (
    Tag, TagAssignment, TagStatus, UnregisteredInventory,
    UnregisteredInventoryStatus, Vehicle, VehicleType,
)

URL = '/api/v1/vehicles/tags/scan-lookup/'


class ScanLookupTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.operator = User.objects.create_user(
            phone='03001234567', password='x', full_name='Operator',
            user_role=UserRole.OPERATOR,
        )
        self.client.force_authenticate(user=self.operator)

    def _lookup(self, **params):
        response = self.client.get(URL, params)
        return response.status_code, response.json().get('data', {})

    def _free_tag(self, serial='TAG001', tid='E280110520008081E83C0B67'):
        return Tag.objects.create(
            tag_serial=serial, tid=tid, status=TagStatus.ACTIVE,
            expiry_date=timezone.now().date() + timedelta(days=365),
        )

    # ── The two answers that matter ──────────────────────────────────────────

    def test_a_free_tag_reports_available_with_its_serial(self):
        """The serial is what the operator must type into the form."""
        self._free_tag()
        status, data = self._lookup(tid='E280110520008081E83C0B67')
        self.assertEqual(status, 200)
        self.assertTrue(data['available'])
        self.assertEqual(data['status'], 'available')
        self.assertEqual(data['tag_serial'], 'TAG001')

    def test_a_tag_already_on_a_vehicle_is_refused_and_names_the_plate(self):
        """Issuing it twice would bill one customer for another's trips."""
        owner = User.objects.create_user(
            phone='03009999999', password='x', full_name='Owner',
            user_role=UserRole.USER,
        )
        vehicle = Vehicle.objects.create(
            plate_number='ABC123', vehicle_type=VehicleType.CAR, owner=owner,
        )
        Account.objects.create(vehicle=vehicle, user=owner, balance=0)
        tag = self._free_tag()
        tag.vehicle = vehicle
        tag.save()

        status, data = self._lookup(tid=tag.tid)
        self.assertEqual(status, 200)
        self.assertFalse(data['available'])
        self.assertEqual(data['status'], 'already_issued')
        self.assertEqual(data['assigned_plate'], 'ABC123')
        self.assertIn('ABC123', data['message'])

    # ── Inventory-only tags (no Tag row yet) ─────────────────────────────────

    def test_a_tag_in_inventory_is_offered_for_issue(self):
        UnregisteredInventory.objects.create(
            tag_serial='INV900', tid='TID900', epc='EPC900',
            status=UnregisteredInventoryStatus.BOOTH_ASSIGNED, booth_assigned_id=4,
        )
        status, data = self._lookup(tid='TID900')
        self.assertEqual(status, 200)
        self.assertTrue(data['available'])
        self.assertEqual(data['status'], 'in_inventory')
        self.assertEqual(data['tag_serial'], 'INV900')
        self.assertEqual(data['booth_assigned_id'], 4)

    def test_an_already_activated_inventory_tag_is_refused(self):
        UnregisteredInventory.objects.create(
            tag_serial='INV901', tid='TID901',
            status=UnregisteredInventoryStatus.ACTIVATED, vehicle_plate='XYZ789',
        )
        status, data = self._lookup(tid='TID901')
        self.assertFalse(data['available'])
        self.assertEqual(data['status'], 'already_activated')
        self.assertEqual(data['assigned_plate'], 'XYZ789')

    def test_an_unknown_tag_is_reported_not_silently_accepted(self):
        status, data = self._lookup(tid='NOSUCHTID')
        self.assertEqual(status, 200)
        self.assertFalse(data['available'])
        self.assertEqual(data['status'], 'not_in_inventory')
        self.assertFalse(data['in_inventory'])

    def test_a_suspended_tag_is_refused(self):
        tag = self._free_tag()
        tag.status = TagStatus.SUSPENDED
        tag.save()
        _, data = self._lookup(tid=tag.tid)
        self.assertFalse(data['available'])
        self.assertEqual(data['status'], 'tag_not_active')

    # ── What readers actually send ───────────────────────────────────────────

    def test_lowercase_and_spaced_tids_from_a_reader_still_match(self):
        """Readers format hex inconsistently; the operator should never care."""
        self._free_tag(tid='E280110520008081E83C0B67')
        _, data = self._lookup(tid='e2 80 11 05 20 00 80 81 e8 3c 0b 67')
        self.assertTrue(data['available'], data)
        self.assertEqual(data['tag_serial'], 'TAG001')

    def test_epc_alone_resolves_when_the_reader_reports_no_tid(self):
        UnregisteredInventory.objects.create(
            tag_serial='INV902', tid='TID902', epc='EPCONLY1',
            status=UnregisteredInventoryStatus.UNREGISTERED,
        )
        _, data = self._lookup(epc='EPCONLY1')
        self.assertTrue(data['available'])
        self.assertEqual(data['tag_serial'], 'INV902')

    def test_tid_wins_over_epc_because_epc_can_be_rewritten(self):
        self._free_tag(serial='BYTID', tid='TIDWINS')
        UnregisteredInventory.objects.create(
            tag_serial='BYEPC', tid='OTHERTID', epc='SHAREDEPC',
            status=UnregisteredInventoryStatus.UNREGISTERED,
        )
        _, data = self._lookup(tid='TIDWINS', epc='SHAREDEPC')
        self.assertEqual(data['tag_serial'], 'BYTID')

    def test_a_lookup_never_changes_anything(self):
        """A scan is a question, not an action."""
        tag = self._free_tag()
        self._lookup(tid=tag.tid)
        tag.refresh_from_db()
        self.assertIsNone(tag.vehicle_id)
        self.assertEqual(tag.status, TagStatus.ACTIVE)

    # ── Access ───────────────────────────────────────────────────────────────

    def test_neither_tid_nor_epc_is_a_bad_request(self):
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 400)

    def test_a_consumer_cannot_enumerate_tags(self):
        consumer = User.objects.create_user(
            phone='03007777777', password='x', full_name='C', user_role=UserRole.USER,
        )
        self.client.force_authenticate(user=consumer)
        self.assertEqual(self.client.get(URL, {'tid': 'X'}).status_code, 403)

    def test_anonymous_is_rejected(self):
        self.client.force_authenticate(user=None)
        self.assertIn(self.client.get(URL, {'tid': 'X'}).status_code, (401, 403))


class StockVsRetiredTests(TestCase):
    """DEACTIVATED + unassigned means two different things in this system.

    TagBulkCreateView inserts stock that way ("inventory tags", per its
    docstring) and TagReissueView flips whatever unassigned tag it picks to
    ACTIVE on issue — so deactivated stock IS issuable. A tag taken OFF a
    vehicle lands in the same state but was replaced for a reason. Assignment
    history is the only thing separating them.
    """

    def setUp(self):
        self.client = APIClient()
        operator = User.objects.create_user(
            phone='03001234567', password='x', full_name='Operator',
            user_role=UserRole.OPERATOR,
        )
        self.client.force_authenticate(user=operator)
        self.owner = operator

    def _stock_tag(self, serial='01092611350001', tid='E280110520008053E83F0B67'):
        """Exactly what TagBulkCreateView writes."""
        return Tag.objects.create(
            tag_serial=serial, tid=tid, vehicle=None,
            status=TagStatus.DEACTIVATED, expiry_date=date(2099, 12, 31),
        )

    def _lookup(self, tid):
        return self.client.get(URL, {'tid': tid}).json()['data']

    def test_bulk_created_stock_is_issuable(self):
        """Regression: this was refused, so a whole box of new tags was unusable."""
        tag = self._stock_tag()
        data = self._lookup(tag.tid)
        self.assertTrue(data['available'], data)
        self.assertEqual(data['status'], 'in_stock')
        self.assertEqual(data['tag_serial'], '01092611350001')

    def test_a_retired_tag_is_not_offered_and_says_where_it_came_from(self):
        tag = self._stock_tag(serial='OLD001', tid='TIDOLD001')
        TagAssignment.objects.create(
            tag=tag, tag_serial=tag.tag_serial, plate_number='ABC123',
            assigned_at=timezone.now() - timedelta(days=60),
            removed_at=timezone.now() - timedelta(days=1),
            removed_reason='reissued; replaced by NEW002',
        )
        data = self._lookup(tag.tid)
        self.assertFalse(data['available'])
        self.assertEqual(data['status'], 'previously_issued')
        self.assertEqual(data['assigned_plate'], 'ABC123')
        self.assertIn('ABC123', data['message'])

    def test_a_suspended_tag_is_still_refused(self):
        """Only DEACTIVATED means stock; SUSPENDED is a real block."""
        tag = self._stock_tag(serial='SUS001', tid='TIDSUS001')
        tag.status = TagStatus.SUSPENDED
        tag.save()
        data = self._lookup(tag.tid)
        self.assertFalse(data['available'])
        self.assertEqual(data['status'], 'tag_not_active')


class AvailableTagsDropdownTests(TestCase):
    """The registration dropdown reads from the same notion of 'issuable'."""

    def setUp(self):
        self.client = APIClient()
        self.operator = User.objects.create_user(
            phone='03001234567', password='x', full_name='Operator',
            user_role=UserRole.OPERATOR,
        )
        self.client.force_authenticate(user=self.operator)

    def _serials(self):
        return [t['tag_serial'] for t in self.client.get(
            '/api/v1/vehicles/tags/available/').json()['data']]

    def test_bulk_created_stock_appears(self):
        """Regression: the dropdown filtered on ACTIVE and so was always empty."""
        Tag.objects.create(
            tag_serial='STOCK001', tid='TIDSTOCK1', vehicle=None,
            status=TagStatus.DEACTIVATED, expiry_date=date(2099, 12, 31),
        )
        self.assertIn('STOCK001', self._serials())

    def test_an_active_unassigned_tag_still_appears(self):
        Tag.objects.create(
            tag_serial='ACTIVE001', tid='TIDACTIVE1', vehicle=None,
            status=TagStatus.ACTIVE, expiry_date=date(2099, 12, 31),
        )
        self.assertIn('ACTIVE001', self._serials())

    def test_a_retired_tag_is_left_out(self):
        tag = Tag.objects.create(
            tag_serial='RETIRED001', tid='TIDRET1', vehicle=None,
            status=TagStatus.DEACTIVATED, expiry_date=date(2099, 12, 31),
        )
        TagAssignment.objects.create(
            tag=tag, tag_serial=tag.tag_serial, plate_number='XYZ999',
            assigned_at=timezone.now() - timedelta(days=30),
            removed_at=timezone.now(),
        )
        self.assertNotIn('RETIRED001', self._serials())

    def test_an_issued_tag_is_left_out(self):
        vehicle = Vehicle.objects.create(
            plate_number='ABC123', vehicle_type=VehicleType.CAR, owner=self.operator,
        )
        Tag.objects.create(
            tag_serial='ONCAR001', tid='TIDONCAR1', vehicle=vehicle,
            status=TagStatus.ACTIVE, expiry_date=date(2099, 12, 31),
        )
        self.assertNotIn('ONCAR001', self._serials())

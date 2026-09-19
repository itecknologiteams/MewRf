"""The money path: entry → exit → charge.

This is the code that takes people's money, and until now nothing exercised it.
The cases below are the ones where a bug costs real money in one direction or
the other — double charges, free passage, a balance moved without an audit row,
or a paying customer turned away at the barrier.
"""

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import (
    Account, Transaction, TransactionStatus, TransactionType,
)
from apps.tolls.models import (
    FareMatrix, Plaza, TollLane, TollTrip, TripStatus,
)
from apps.tolls.services import (
    MINIMUM_BALANCE, EntryService, ExitService, invalidate_rate_cache,
)
from apps.users.models import User, UserRole
from apps.vehicles.models import (
    Tag, TagStatus, Vehicle, VehicleCategory, VehicleStatus, VehicleType,
)

CAR_FARE = Decimal('100.00')
BUS_FARE = Decimal('250.00')


# ENTRY_AUTO_RESET_ACTIVE_TRIP is a developer convenience set only in
# config.settings.local: it deletes any open trip so the same tag can re-enter
# over and over. Tests inherit that module, so without pinning it off here every
# duplicate-entry assertion below would pass vacuously while testing the
# opposite of what booths and master actually run (config.settings.lan, where
# the flag is absent and the getattr default of False applies).
@override_settings(ENTRY_AUTO_RESET_ACTIVE_TRIP=False)
class TollFlowTestCase(TestCase):
    """One vehicle, two plazas, a fare between them."""

    def setUp(self):
        # The rate cache is a module-level dict with a 10-minute TTL, so a fare
        # read in one test would otherwise still be served in the next one —
        # including after that test changed or deleted it.
        invalidate_rate_cache()
        self.addCleanup(invalidate_rate_cache)

        self.owner = User.objects.create_user(
            phone='03001234567', password='x', full_name='Owner',
            user_role=UserRole.USER,
        )
        self.entry_plaza = Plaza.objects.create(plaza_id=1, name='Qayumabad')
        self.exit_plaza = Plaza.objects.create(plaza_id=2, name='Quaidabad')
        self.entry_lane = TollLane.objects.create(plaza=self.entry_plaza, lane_number=1)
        self.exit_lane = TollLane.objects.create(plaza=self.exit_plaza, lane_number=1)

        self.car_category = VehicleCategory.objects.create(
            category_index=1, code=VehicleType.CAR, name='Car',
        )
        FareMatrix.objects.create(
            from_plaza=self.entry_plaza, to_plaza=self.exit_plaza,
            category=self.car_category, fare=CAR_FARE,
        )

        self.vehicle, self.account, self.tag = self._make_vehicle('ABC123', 'TID0001')

    def _make_vehicle(self, plate, tid, balance='1000.00', vehicle_type=VehicleType.CAR):
        vehicle = Vehicle.objects.create(
            plate_number=plate, vehicle_type=vehicle_type, owner=self.owner,
        )
        account = Account.objects.create(
            vehicle=vehicle, user=self.owner, balance=Decimal(balance),
        )
        tag = Tag.objects.create(
            tag_serial=f'SER{tid}', tid=tid, vehicle=vehicle,
            status=TagStatus.ACTIVE,
            expiry_date=timezone.now().date() + timedelta(days=365),
        )
        return vehicle, account, tag

    def _enter(self, tid=None, lane=None):
        return EntryService.process_entry(
            tid or self.tag.tid, self.entry_plaza.id,
            (lane or self.entry_lane).id,
        )

    def _exit(self, tid=None, lane=None):
        return ExitService.process_exit(
            tid or self.tag.tid, self.exit_plaza.id,
            (lane or self.exit_lane).id,
        )

    def _balance(self):
        self.account.refresh_from_db()
        return self.account.balance


class EntryTests(TollFlowTestCase):
    def test_entry_opens_a_trip_and_takes_no_money(self):
        result = self._enter()
        self.assertTrue(result['success'], result)

        trip = TollTrip.objects.get()
        self.assertEqual(trip.status, TripStatus.ACTIVE)
        self.assertEqual(trip.entry_plaza, self.entry_plaza)
        self.assertEqual(trip.entry_lane, self.entry_lane)
        self.assertIsNone(trip.exit_time)
        self.assertIsNone(trip.charge_amount)
        # Entry is free; the toll is taken at exit.
        self.assertEqual(self._balance(), Decimal('1000.00'))
        self.assertFalse(Transaction.objects.exists())

    def test_unknown_tag_is_refused(self):
        result = EntryService.process_entry('NOSUCHTID', self.entry_plaza.id)
        self.assertFalse(result['success'])
        self.assertEqual(result['reason'], 'Tag not found')
        self.assertFalse(TollTrip.objects.exists())

    def test_unassigned_tag_is_refused(self):
        self.tag.vehicle = None
        self.tag.save()
        result = self._enter()
        self.assertFalse(result['success'])
        self.assertEqual(result['reason'], 'Tag not assigned to any vehicle')

    def test_inactive_tag_is_refused(self):
        self.tag.status = TagStatus.SUSPENDED
        self.tag.save()
        result = self._enter()
        self.assertFalse(result['success'])
        self.assertIn('Tag is', result['reason'])
        self.assertFalse(TollTrip.objects.exists())

    def test_expired_tag_is_refused(self):
        self.tag.expiry_date = timezone.now().date() - timedelta(days=1)
        self.tag.save()
        result = self._enter()
        self.assertFalse(result['success'])
        self.assertEqual(result['reason'], 'Tag expired')

    def test_non_active_vehicle_is_refused(self):
        self.vehicle.status = VehicleStatus.SUSPENDED
        self.vehicle.save()
        result = self._enter()
        self.assertFalse(result['success'])
        self.assertIn('Vehicle is', result['reason'])

    def test_balance_below_the_minimum_is_refused_with_the_shortfall(self):
        self.account.balance = MINIMUM_BALANCE - Decimal('0.01')
        self.account.save()
        result = self._enter()
        self.assertFalse(result['success'])
        self.assertEqual(result['reason'], 'Insufficient balance')
        # The display shows these to the driver, so they must be present.
        self.assertEqual(result['current_balance'], str(self.account.balance))
        self.assertEqual(result['minimum_required'], str(MINIMUM_BALANCE))
        self.assertFalse(TollTrip.objects.exists())

    def test_balance_exactly_at_the_minimum_is_allowed(self):
        """`<` not `<=` — a driver holding exactly the minimum gets through."""
        self.account.balance = MINIMUM_BALANCE
        self.account.save()
        self.assertTrue(self._enter()['success'])

    def test_second_entry_while_a_trip_is_open_is_refused(self):
        """Otherwise one vehicle accumulates trips and only the last is billed."""
        self.assertTrue(self._enter()['success'])
        result = self._enter()
        self.assertFalse(result['success'])
        self.assertEqual(result['reason'], 'Vehicle already has an active trip')
        self.assertEqual(TollTrip.objects.count(), 1)

    @override_settings(ENTRY_AUTO_RESET_ACTIVE_TRIP=True)
    def test_the_dev_auto_reset_flag_replaces_the_open_trip(self):
        """What config.settings.local turns on — and why lan must not.

        With this on, a re-entry silently deletes the open trip: the first
        passage is erased and never billed. Harmless on a developer's machine,
        revenue loss on a booth.
        """
        self._enter()
        first_trip_id = TollTrip.objects.get().id
        self.assertTrue(self._enter()['success'])
        self.assertEqual(TollTrip.objects.count(), 1)
        self.assertNotEqual(TollTrip.objects.get().id, first_trip_id)

    def test_the_auto_reset_flag_is_off_in_the_settings_booths_run(self):
        """Booths and master run config.settings.lan; it must not enable this."""
        from config.settings import lan
        self.assertFalse(getattr(lan, 'ENTRY_AUTO_RESET_ACTIVE_TRIP', False))

    def test_re_entry_after_a_completed_trip_is_allowed(self):
        self._enter()
        self._exit()
        self.assertTrue(self._enter()['success'])
        self.assertEqual(TollTrip.objects.filter(status=TripStatus.ACTIVE).count(), 1)

    def test_an_unknown_lane_does_not_block_entry(self):
        """Lane is for reporting; a bad lane id must not turn a vehicle away."""
        result = EntryService.process_entry(self.tag.tid, self.entry_plaza.id, 999999)
        self.assertTrue(result['success'], result)
        self.assertIsNone(TollTrip.objects.get().entry_lane)


class ExitTests(TollFlowTestCase):
    def test_exit_charges_the_fare_and_closes_the_trip(self):
        self._enter()
        result = self._exit()
        self.assertTrue(result['success'], result)

        trip = TollTrip.objects.get()
        self.assertEqual(trip.status, TripStatus.COMPLETED)
        self.assertEqual(trip.exit_plaza, self.exit_plaza)
        self.assertEqual(trip.exit_lane, self.exit_lane)
        self.assertIsNotNone(trip.exit_time)
        self.assertEqual(trip.charge_amount, CAR_FARE)
        self.assertEqual(trip.balance_before, Decimal('1000.00'))
        self.assertEqual(trip.balance_after, Decimal('900.00'))
        self.assertEqual(self._balance(), Decimal('900.00'))
        self.assertEqual(result['charge'], str(CAR_FARE))
        self.assertEqual(result['balance_remaining'], '900.00')

    def test_exit_writes_one_audit_transaction_that_matches_the_charge(self):
        """A balance that moves without a matching ledger row is unauditable."""
        self._enter()
        self._exit()

        txn = Transaction.objects.get()
        self.assertEqual(txn.account, self.account)
        self.assertEqual(txn.amount, CAR_FARE)
        self.assertEqual(txn.transaction_type, TransactionType.TOLL_DEDUCTION)
        self.assertEqual(txn.status, TransactionStatus.SUCCESS)
        self.assertEqual(txn.balance_before, Decimal('1000.00'))
        self.assertEqual(txn.balance_after, Decimal('900.00'))
        self.assertEqual(txn.balance_before - txn.amount, txn.balance_after)
        self.assertEqual(txn.toll_trip, TollTrip.objects.get())

    def test_exit_without_an_entry_is_refused(self):
        result = self._exit()
        self.assertFalse(result['success'])
        self.assertEqual(result['reason'], 'No active trip found for this vehicle')
        self.assertEqual(self._balance(), Decimal('1000.00'))
        self.assertFalse(Transaction.objects.exists())

    def test_a_second_exit_does_not_charge_twice(self):
        """The single most expensive bug available here."""
        self._enter()
        self.assertTrue(self._exit()['success'])
        balance_after_first = self._balance()

        second = self._exit()
        self.assertFalse(second['success'])
        self.assertEqual(self._balance(), balance_after_first)
        self.assertEqual(Transaction.objects.count(), 1)
        self.assertEqual(TollTrip.objects.filter(status=TripStatus.COMPLETED).count(), 1)

    def test_a_route_with_no_fare_is_refused_and_charges_nothing(self):
        FareMatrix.objects.all().delete()
        invalidate_rate_cache()
        self._enter()

        result = self._exit()
        self.assertFalse(result['success'])
        self.assertEqual(result['reason'], 'Toll rate not configured for this route')
        self.assertEqual(self._balance(), Decimal('1000.00'))
        self.assertFalse(Transaction.objects.exists())
        # The trip stays open so the passage is not silently lost.
        self.assertEqual(TollTrip.objects.get().status, TripStatus.ACTIVE)

    def test_insufficient_balance_at_exit_leaves_everything_untouched(self):
        self.account.balance = CAR_FARE - Decimal('0.01')
        self.account.save()
        self._enter()

        result = self._exit()
        self.assertFalse(result['success'])
        self.assertEqual(result['reason'], 'Insufficient balance at exit')
        self.assertEqual(result['charge'], str(CAR_FARE))
        self.assertEqual(self._balance(), CAR_FARE - Decimal('0.01'))
        self.assertFalse(Transaction.objects.exists())
        self.assertEqual(TollTrip.objects.get().status, TripStatus.ACTIVE)

    def test_balance_exactly_equal_to_the_fare_is_allowed_to_zero(self):
        self.account.balance = CAR_FARE
        self.account.save()
        self._enter()
        self.assertTrue(self._exit()['success'])
        self.assertEqual(self._balance(), Decimal('0.00'))

    def test_the_fare_billed_follows_the_vehicles_category(self):
        bus_category = VehicleCategory.objects.create(
            category_index=4, code=VehicleType.LARGE_BUS, name='Large Bus',
        )
        FareMatrix.objects.create(
            from_plaza=self.entry_plaza, to_plaza=self.exit_plaza,
            category=bus_category, fare=BUS_FARE,
        )
        _, bus_account, bus_tag = self._make_vehicle(
            'BUS999', 'TID0002', vehicle_type=VehicleType.LARGE_BUS,
        )

        EntryService.process_entry(bus_tag.tid, self.entry_plaza.id)
        ExitService.process_exit(bus_tag.tid, self.exit_plaza.id)

        bus_account.refresh_from_db()
        self.assertEqual(bus_account.balance, Decimal('1000.00') - BUS_FARE)
        # The car alongside it is unaffected and still billed the car fare.
        self._enter()
        self._exit()
        self.assertEqual(self._balance(), Decimal('1000.00') - CAR_FARE)

    def test_a_deactivated_category_stops_billing_rather_than_charging_zero(self):
        self.car_category.is_active = False
        self.car_category.save()
        invalidate_rate_cache()
        self._enter()

        result = self._exit()
        self.assertFalse(result['success'])
        self.assertEqual(self._balance(), Decimal('1000.00'))

    def test_the_reverse_direction_is_a_separate_fare(self):
        """(A→B) and (B→A) are distinct rows; a missing reverse must not bill A→B's."""
        EntryService.process_entry(self.tag.tid, self.exit_plaza.id)
        result = ExitService.process_exit(self.tag.tid, self.entry_plaza.id)
        self.assertFalse(result['success'])
        self.assertEqual(result['reason'], 'Toll rate not configured for this route')
        self.assertEqual(self._balance(), Decimal('1000.00'))

    def test_an_unknown_lane_does_not_block_exit_or_the_charge(self):
        self._enter()
        result = ExitService.process_exit(self.tag.tid, self.exit_plaza.id, 999999)
        self.assertTrue(result['success'], result)
        self.assertEqual(self._balance(), Decimal('900.00'))
        self.assertIsNone(TollTrip.objects.get().exit_lane)


class RateCacheTests(TollFlowTestCase):
    """The fare cache is a process-global dict with a 10-minute TTL."""

    def test_a_fare_change_is_not_billed_until_the_cache_is_invalidated(self):
        """Pins the reason every admin fare write must call invalidate_rate_cache."""
        self._enter()
        self._exit()
        self.assertEqual(self._balance(), Decimal('900.00'))

        FareMatrix.objects.update(fare=Decimal('500.00'))
        self._enter()
        self._exit()
        # Still the cached 100 — the stale read is real, which is why the admin
        # rate views clear the cache on every write.
        self.assertEqual(self._balance(), Decimal('800.00'))

        invalidate_rate_cache()
        self._enter()
        self._exit()
        self.assertEqual(self._balance(), Decimal('300.00'))

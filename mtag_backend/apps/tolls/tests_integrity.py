"""Performance and data-integrity properties of the toll path.

The query counts here are budgets, not measurements: a lane processes a vehicle
while it is physically at the barrier, so an accidental N+1 in the entry or exit
path shows up as a queue, not as a slow page. The integrity tests assert the
invariants an auditor would check — that every rupee moved has a ledger row
explaining it.
"""

from datetime import timedelta
from decimal import Decimal

from django.db import connection
from django.db.models import Sum
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.accounts.models import Account, Transaction, TransactionType
from apps.tolls.models import FareMatrix, Plaza, TollLane, TollTrip, TripStatus
from apps.tolls.services import EntryService, ExitService, invalidate_rate_cache
from apps.users.models import User, UserRole
from apps.vehicles.models import Tag, TagStatus, Vehicle, VehicleCategory, VehicleType

CAR_FARE = Decimal('100.00')


@override_settings(ENTRY_AUTO_RESET_ACTIVE_TRIP=False)
class TollPathTestCase(TestCase):
    def setUp(self):
        invalidate_rate_cache()
        self.addCleanup(invalidate_rate_cache)

        self.owner = User.objects.create_user(
            phone='03001234567', password='x', full_name='Owner',
            user_role=UserRole.USER,
        )
        self.plaza_a = Plaza.objects.create(plaza_id=1, name='A')
        self.plaza_b = Plaza.objects.create(plaza_id=2, name='B')
        self.lane_a = TollLane.objects.create(plaza=self.plaza_a, lane_number=1)
        self.lane_b = TollLane.objects.create(plaza=self.plaza_b, lane_number=1)
        self.category = VehicleCategory.objects.create(
            category_index=1, code=VehicleType.CAR, name='Car',
        )
        FareMatrix.objects.create(
            from_plaza=self.plaza_a, to_plaza=self.plaza_b,
            category=self.category, fare=CAR_FARE,
        )

    def _vehicle(self, plate, tid, balance='10000.00'):
        vehicle = Vehicle.objects.create(
            plate_number=plate, vehicle_type=VehicleType.CAR, owner=self.owner,
        )
        account = Account.objects.create(
            vehicle=vehicle, user=self.owner, balance=Decimal(balance),
        )
        tag = Tag.objects.create(
            tag_serial=f'SER{tid}', tid=tid, vehicle=vehicle, status=TagStatus.ACTIVE,
            expiry_date=timezone.now().date() + timedelta(days=365),
        )
        return vehicle, account, tag


class QueryBudgetTests(TollPathTestCase):
    """A vehicle is at the barrier while these run. Queries are the cost."""

    def test_entry_query_count_is_bounded(self):
        _, _, tag = self._vehicle('ABC123', 'TID1')
        # Measured, not guessed: tag+vehicle, active-trip check, lane, insert,
        # plus the savepoints the atomic block opens.
        with self.assertNumQueries(7):
            result = EntryService.process_entry(tag.tid, self.plaza_a.id, self.lane_a.id)
        self.assertTrue(result['success'], result)

    def test_exit_query_count_is_bounded(self):
        _, _, tag = self._vehicle('ABC124', 'TID2')
        EntryService.process_entry(tag.tid, self.plaza_a.id, self.lane_a.id)
        # Cold: the fare row is read from the database on this first exit.
        with self.assertNumQueries(11):
            result = ExitService.process_exit(tag.tid, self.plaza_b.id, self.lane_b.id)
        self.assertTrue(result['success'], result)

    def test_the_fare_cache_saves_a_query_on_the_second_vehicle(self):
        """Every exit would otherwise re-read the same fare row.

        Measured rather than hardcoded, so this states the property (the warm
        path is cheaper) instead of a number that moves whenever the exit path
        gains a query for an unrelated reason.
        """
        counts = []
        for i, plate in enumerate(('ABC201', 'ABC202')):
            _, _, tag = self._vehicle(plate, f'TIDC{i}')
            EntryService.process_entry(tag.tid, self.plaza_a.id)
            with CaptureQueriesContext(connection) as captured:
                ExitService.process_exit(tag.tid, self.plaza_b.id)
            counts.append(len(captured))

        cold, warm = counts
        self.assertEqual(warm, cold - 1, f"cold={cold} warm={warm}")

    def test_a_refused_entry_costs_less_than_an_accepted_one(self):
        """A denied vehicle must not be the expensive case at a busy lane."""
        with self.assertNumQueries(3):
            EntryService.process_entry('NOSUCHTAG', self.plaza_a.id)


class LedgerIntegrityTests(TollPathTestCase):
    """Every rupee that moves must have a row explaining it."""

    def _run_trips(self, count):
        for i in range(count):
            _, account, tag = self._vehicle(f'PLT{i:04d}', f'TIDL{i}')
            EntryService.process_entry(tag.tid, self.plaza_a.id, self.lane_a.id)
            ExitService.process_exit(tag.tid, self.plaza_b.id, self.lane_b.id)

    def test_every_completed_trip_has_exactly_one_deduction(self):
        self._run_trips(5)
        completed = TollTrip.objects.filter(status=TripStatus.COMPLETED)
        self.assertEqual(completed.count(), 5)
        for trip in completed:
            self.assertEqual(
                Transaction.objects.filter(
                    toll_trip=trip, transaction_type=TransactionType.TOLL_DEDUCTION,
                ).count(),
                1,
                f"trip {trip.id} must have exactly one deduction",
            )

    def test_revenue_recorded_equals_revenue_charged(self):
        """The audit ledger and the trips must agree on the total taken."""
        self._run_trips(5)
        charged = TollTrip.objects.filter(
            status=TripStatus.COMPLETED,
        ).aggregate(total=Sum('charge_amount'))['total']
        ledgered = Transaction.objects.filter(
            transaction_type=TransactionType.TOLL_DEDUCTION,
        ).aggregate(total=Sum('amount'))['total']
        self.assertEqual(charged, ledgered)
        self.assertEqual(charged, CAR_FARE * 5)

    def test_each_balance_equals_its_opening_balance_less_its_ledger(self):
        self._run_trips(3)
        for account in Account.objects.all():
            spent = account.transactions.filter(
                transaction_type=TransactionType.TOLL_DEDUCTION,
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            self.assertEqual(account.balance, Decimal('10000.00') - spent)

    def test_ledger_rows_chain_without_gaps(self):
        """balance_before - amount == balance_after on every row."""
        self._run_trips(3)
        for txn in Transaction.objects.all():
            self.assertEqual(
                txn.balance_before - txn.amount, txn.balance_after,
                f"transaction {txn.id} does not reconcile",
            )

    def test_no_trip_is_completed_without_a_charge_recorded(self):
        """A completed trip with a null charge is untraceable free passage."""
        self._run_trips(3)
        self.assertFalse(
            TollTrip.objects.filter(
                status=TripStatus.COMPLETED, charge_amount__isnull=True,
            ).exists()
        )

    def test_no_orphan_deduction_exists_without_a_trip(self):
        self._run_trips(3)
        self.assertFalse(
            Transaction.objects.filter(
                transaction_type=TransactionType.TOLL_DEDUCTION, toll_trip__isnull=True,
            ).exists()
        )

    def test_a_refused_exit_leaves_no_partial_record(self):
        """The atomic block must roll back the balance AND the trip together."""
        _, account, tag = self._vehicle('PART01', 'TIDP1', balance='50.00')
        EntryService.process_entry(tag.tid, self.plaza_a.id)
        result = ExitService.process_exit(tag.tid, self.plaza_b.id)

        self.assertFalse(result['success'])
        account.refresh_from_db()
        self.assertEqual(account.balance, Decimal('50.00'))
        self.assertFalse(Transaction.objects.exists())
        trip = TollTrip.objects.get()
        self.assertEqual(trip.status, TripStatus.ACTIVE)
        self.assertIsNone(trip.charge_amount)
        self.assertIsNone(trip.balance_after)


class ConcurrencyIntegrityTests(TollPathTestCase):
    """One vehicle cannot be billed twice for one passage."""

    def test_repeated_exits_in_sequence_charge_exactly_once(self):
        _, account, tag = self._vehicle('RACE01', 'TIDR1')
        EntryService.process_entry(tag.tid, self.plaza_a.id)

        results = [ExitService.process_exit(tag.tid, self.plaza_b.id) for _ in range(5)]
        self.assertEqual(sum(1 for r in results if r['success']), 1)

        account.refresh_from_db()
        self.assertEqual(account.balance, Decimal('10000.00') - CAR_FARE)
        self.assertEqual(Transaction.objects.count(), 1)

    def test_repeated_entries_open_exactly_one_trip(self):
        _, _, tag = self._vehicle('RACE02', 'TIDR2')
        results = [
            EntryService.process_entry(tag.tid, self.plaza_a.id) for _ in range(5)
        ]
        self.assertEqual(sum(1 for r in results if r['success']), 1)
        self.assertEqual(TollTrip.objects.count(), 1)

"""Consumer-facing toll surface: trip-history ownership, and fare-matrix reads.

The fare tests pin the join key the app uses to answer "what will this trip cost
*my* car": FareSerializer.category_code mirrors Vehicle.vehicle_type. If that
mapping ever drifts, the app silently quotes the wrong fare class, which is worse
than failing.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Account
from apps.users.models import User, UserRole
from apps.vehicles.models import Tag, TagStatus, Vehicle, VehicleCategory
from .models import FareMatrix, Plaza, TollTrip, TripStatus


def make_holder(phone, plate, vehicle_type='car'):
    user = User.objects.create_user(
        phone=phone, password='holderpass123', full_name=f'Holder {phone}'
    )
    vehicle = Vehicle.objects.create(
        owner=user, plate_number=plate, vehicle_type=vehicle_type
    )
    account = Account.objects.create(
        vehicle=vehicle, user=user, balance=Decimal('1000.00')
    )
    tag = Tag.objects.create(
        tag_serial=f'SER{plate}', tid=f'TID{plate}', vehicle=vehicle,
        expiry_date=date(2099, 12, 31), status=TagStatus.ACTIVE,
    )
    return user, vehicle, account, tag


class TripHistoryOwnershipTest(TestCase):
    def setUp(self):
        self.entry = Plaza.objects.create(plaza_id=1, name='Shahfaisal Main Toll Plaza')
        self.exit = Plaza.objects.create(plaza_id=2, name='Kathor Main Toll Plaza')

        self.mine = make_holder('03001112233', 'KDE1836')
        self.theirs = make_holder('03004445566', 'ABC1234')

        for holder, charge in ((self.mine, '120.00'), (self.theirs, '777.00')):
            TollTrip.objects.create(
                vehicle=holder[1], tag=holder[3], account=holder[2],
                entry_plaza=self.entry, exit_plaza=self.exit,
                exit_time=timezone.now(), charge_amount=Decimal(charge),
                balance_before=Decimal('1000.00'),
                balance_after=Decimal('1000.00') - Decimal(charge),
                status=TripStatus.COMPLETED,
            )

        self.client = APIClient()
        self.client.force_authenticate(user=self.mine[0])

    def test_own_trips_readable(self):
        response = self.client.get(f'/api/v1/tolls/trips/{self.mine[1].id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.json()['data']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['charge_amount'], '120.00')
        self.assertEqual(rows[0]['entry_plaza_name'], 'Shahfaisal Main Toll Plaza')
        self.assertEqual(rows[0]['exit_plaza_name'], 'Kathor Main Toll Plaza')
        self.assertIsNotNone(rows[0]['duration_minutes'])

    def test_another_holders_trips_are_not_returned(self):
        response = self.client.get(f'/api/v1/tolls/trips/{self.theirs[1].id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['data'], [])
        self.assertNotIn('777.00', response.content.decode())

    def test_operator_keeps_access(self):
        operator = User.objects.create_user(
            phone='03007776655', password='oppass123456', full_name='Operator',
            user_role=UserRole.OPERATOR,
        )
        client = APIClient()
        client.force_authenticate(user=operator)
        response = client.get(f'/api/v1/tolls/trips/{self.theirs[1].id}/')
        self.assertEqual(len(response.json()['data']), 1)

    def test_active_trip_has_no_exit_and_no_charge(self):
        """The app renders this as a distinct live card."""
        TollTrip.objects.filter(vehicle=self.mine[1]).delete()
        TollTrip.objects.create(
            vehicle=self.mine[1], tag=self.mine[3], account=self.mine[2],
            entry_plaza=self.entry, status=TripStatus.ACTIVE,
        )
        row = self.client.get(
            f'/api/v1/tolls/trips/{self.mine[1].id}/'
        ).json()['data'][0]
        self.assertEqual(row['status'], TripStatus.ACTIVE)
        self.assertIsNone(row['exit_plaza_name'])
        self.assertIsNone(row['exit_time'])
        self.assertIsNone(row['charge_amount'])
        self.assertIsNone(row['duration_minutes'])


class FareLookupContractTest(TestCase):
    def setUp(self):
        self.a = Plaza.objects.create(plaza_id=1, name='Shahfaisal Main Toll Plaza')
        self.b = Plaza.objects.create(plaza_id=101, name='Shafaisal-1 Interchange')
        self.car = VehicleCategory.objects.create(
            category_index=1, code='car', name='Car / Jeep / Taxi / Pickup'
        )
        self.truck = VehicleCategory.objects.create(
            category_index=5, code='truck_2axle', name='2 Axle Truck'
        )
        FareMatrix.objects.create(
            from_plaza=self.a, to_plaza=self.b, category=self.car, fare=Decimal('100.00')
        )
        FareMatrix.objects.create(
            from_plaza=self.a, to_plaza=self.b, category=self.truck, fare=Decimal('350.00')
        )
        # Deliberately asymmetric: the app must never assume A->B == B->A.
        FareMatrix.objects.create(
            from_plaza=self.b, to_plaza=self.a, category=self.car, fare=Decimal('120.00')
        )

        self.holder = make_holder('03001112233', 'KDE1836')
        self.client = APIClient()
        self.client.force_authenticate(user=self.holder[0])

    def test_category_code_matches_vehicle_type(self):
        """This is the app's join key from a vehicle to its fare."""
        rows = self.client.get('/api/v1/tolls/rates/').json()['data']
        codes = {r['category_code'] for r in rows}
        self.assertEqual(codes, {'car', 'truck_2axle'})
        for row in rows:
            self.assertIsInstance(row['category'], int)
        car_rows = [r for r in rows if r['category_code'] == 'car']
        self.assertEqual(car_rows[0]['category'], 1)

    def test_fares_are_directional(self):
        rows = self.client.get('/api/v1/tolls/rates/').json()['data']
        forward = next(r for r in rows
                       if r['from_plaza'] == self.a.id and r['to_plaza'] == self.b.id
                       and r['category_code'] == 'car')
        reverse = next(r for r in rows
                       if r['from_plaza'] == self.b.id and r['to_plaza'] == self.a.id
                       and r['category_code'] == 'car')
        self.assertEqual(forward['fare'], '100.00')
        self.assertEqual(reverse['fare'], '120.00')

    def test_display_id_is_zero_padded_and_from_plaza_is_the_row_id(self):
        """`from_plaza` is the row id; `from_plaza_display_id` is the operator's
        number zero-padded. Confusing the two mislabels every fare in the UI."""
        rows = self.client.get('/api/v1/tolls/rates/').json()['data']
        row = next(r for r in rows if r['from_plaza'] == self.a.id)
        self.assertEqual(row['from_plaza_display_id'], '001')
        self.assertEqual(row['to_plaza_display_id'], '101')
        self.assertEqual(row['from_plaza_name'], 'Shahfaisal Main Toll Plaza')

    def test_plaza_list_exposes_plaza_id_separate_from_row_id(self):
        rows = self.client.get('/api/v1/tolls/plazas/').json()['data']
        by_plaza_id = {r['plaza_id']: r for r in rows}
        self.assertIn(101, by_plaza_id)
        self.assertEqual(by_plaza_id[101]['name'], 'Shafaisal-1 Interchange')
        self.assertIn('lanes', by_plaza_id[101])

    def test_vehicle_categories_listed(self):
        rows = self.client.get('/api/v1/tolls/vehicle-categories/').json()['data']
        self.assertEqual({r['code'] for r in rows}, {'car', 'truck_2axle'})


class MyTripListTest(TestCase):
    """GET /tolls/trips/my/ — the union of the caller's vehicles, and nobody else's."""

    def setUp(self):
        self.entry = Plaza.objects.create(plaza_id=1, name='Shahfaisal Main Toll Plaza')
        self.exit = Plaza.objects.create(plaza_id=2, name='Kathor Main Toll Plaza')

        self.user = User.objects.create_user(
            phone='03001112233', password='holderpass123', full_name='Two Car Holder'
        )
        self.stranger, self.other_vehicle, self.other_account, self.other_tag = \
            make_holder('03009998877', 'XYZ9999')

        # TWO vehicles on one account holder, which is the case the per-vehicle endpoint
        # could not serve without the client merging paginated streams itself.
        self.vehicles = []
        for plate in ('KDE1836', 'KDE7777'):
            vehicle = Vehicle.objects.create(
                owner=self.user, plate_number=plate, vehicle_type='car'
            )
            account = Account.objects.create(
                vehicle=vehicle, user=self.user, balance=Decimal('1000.00')
            )
            tag = Tag.objects.create(
                tag_serial=f'SER{plate}', tid=f'TID{plate}', vehicle=vehicle,
                expiry_date=date(2099, 12, 31), status=TagStatus.ACTIVE,
            )
            self.vehicles.append((vehicle, account, tag))

        base = timezone.now()
        # Interleaved in time across the two vehicles, so a result that is merely
        # concatenated per vehicle rather than globally ordered will fail the order test.
        self.expected_plates = []
        for offset, (vehicle, account, tag) in enumerate(
            [self.vehicles[0], self.vehicles[1], self.vehicles[0], self.vehicles[1]]
        ):
            trip = TollTrip.objects.create(
                vehicle=vehicle, tag=tag, account=account,
                entry_plaza=self.entry, exit_plaza=self.exit,
                exit_time=base, charge_amount=Decimal('120.00'),
                balance_before=Decimal('1000.00'), balance_after=Decimal('880.00'),
                status=TripStatus.COMPLETED,
            )
            # entry_time is auto_now_add, so it has to be written after creation.
            TollTrip.objects.filter(pk=trip.pk).update(
                entry_time=base - timedelta(hours=offset)
            )
            self.expected_plates.append(vehicle.plate_number)

        # One open trip, to prove ?status filters rather than being ignored.
        self.active = TollTrip.objects.create(
            vehicle=self.vehicles[0][0], tag=self.vehicles[0][2],
            account=self.vehicles[0][1], entry_plaza=self.entry,
            status=TripStatus.ACTIVE,
        )

        TollTrip.objects.create(
            vehicle=self.other_vehicle, tag=self.other_tag, account=self.other_account,
            entry_plaza=self.entry, exit_plaza=self.exit, exit_time=base,
            charge_amount=Decimal('999.00'), balance_before=Decimal('1000.00'),
            balance_after=Decimal('1.00'), status=TripStatus.COMPLETED,
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_returns_trips_from_every_vehicle_the_caller_owns(self):
        response = self.client.get('/api/v1/tolls/trips/my/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        plates = {row['plate_number'] for row in response.data['data']}
        self.assertEqual(plates, {'KDE1836', 'KDE7777'})

    def test_excludes_other_holders_trips(self):
        response = self.client.get('/api/v1/tolls/trips/my/')
        self.assertNotIn('XYZ9999', {r['plate_number'] for r in response.data['data']})
        # The stranger's charge is distinctive; its absence is the real assertion.
        self.assertNotIn(
            '999.00', {str(r['charge_amount']) for r in response.data['data']}
        )

    def test_newest_first_across_vehicles(self):
        response = self.client.get('/api/v1/tolls/trips/my/')
        times = [r['entry_time'] for r in response.data['data']]
        self.assertEqual(times, sorted(times, reverse=True))

    def test_status_filter_narrows_to_open_trips(self):
        response = self.client.get('/api/v1/tolls/trips/my/?status=active')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 1)
        self.assertEqual(response.data['data'][0]['id'], self.active.id)
        self.assertIsNone(response.data['data'][0]['exit_time'])

    def test_unknown_status_is_refused_not_ignored(self):
        # Silently returning everything would make a client typo look like "no filter
        # needed" and ship a screen that claims to be filtered and is not.
        response = self.client.get('/api/v1/tolls/trips/my/?status=finished')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_anonymous_is_rejected(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(
            self.client.get('/api/v1/tolls/trips/my/').status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_pagination_meta_is_present(self):
        response = self.client.get('/api/v1/tolls/trips/my/?page_size=2')
        self.assertEqual(len(response.data['data']), 2)
        self.assertIn('meta', response.data)
        # 4 completed + 1 active for this holder; the stranger's trip must not be counted.
        self.assertEqual(response.data['meta']['count'], 5)
        self.assertEqual(response.data['meta']['total_pages'], 3)
        self.assertIsNotNone(response.data['meta']['next'])

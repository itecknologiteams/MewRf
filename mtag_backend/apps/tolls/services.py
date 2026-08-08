import logging
import threading
import time
from decimal import Decimal
from django.conf import settings
from django.db import transaction as db_transaction
from django.utils import timezone
from apps.vehicles.models import Tag, TagStatus
from apps.accounts.models import Account, Transaction, TransactionType, TransactionStatus
from django.db.models import F
from .models import TollTrip, FareMatrix, TollLane, TripStatus, DailySummary

logger = logging.getLogger(__name__)

MINIMUM_BALANCE = Decimal('50.00')

# ── In-memory rate cache ──────────────────────────────────────────────────────
# Toll rates change rarely (admin action). Cache them for 10 minutes so every
# exit does not hit the database for the same rate lookup.
_rate_cache: dict = {}
_RATE_CACHE_TTL = 600  # seconds


def _cached_rate(entry_plaza_id, exit_plaza_id, vehicle_type):
    """Fare for a trip, from the fare_matrix table.

    `vehicle_type` is the Vehicle.vehicle_type string; it maps to a category via
    VehicleCategory.code, and fare_matrix joins on that category's index. Only
    active categories bill — deactivating a category takes it out of service
    without deleting its fare history.

    Returns None when no fare row exists, which ExitService reports as
    "Toll rate not configured for this route" rather than guessing an amount.
    """
    key = f"{entry_plaza_id}:{exit_plaza_id}:{vehicle_type}"
    entry = _rate_cache.get(key)
    if entry:
        rate_val, ts = entry
        if time.monotonic() - ts < _RATE_CACHE_TTL:
            return rate_val

    row = FareMatrix.objects.filter(
        from_plaza_id=entry_plaza_id,
        to_plaza_id=exit_plaza_id,
        category__code=vehicle_type,
        category__is_active=True,
    ).values('fare').first()
    if row:
        _rate_cache[key] = (row['fare'], time.monotonic())
        return row['fare']
    return None


def invalidate_rate_cache():
    """Call after any admin creates or updates a toll rate."""
    _rate_cache.clear()
    logger.info("Toll rate cache cleared")


def _bg(fn, *args, **kwargs):
    """Fire-and-forget background thread for non-critical DB writes."""
    threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True).start()


def _update_last_scanned(tag_id):
    try:
        Tag.objects.filter(id=tag_id).update(last_scanned_at=timezone.now())
    except Exception as exc:
        logger.warning("last_scanned_at update failed: %s", exc)


def _inc_summary_entry(plaza_id, lane_id, vehicle_type, date):
    """Atomically increment entry count in daily_summaries."""
    try:
        obj, _ = DailySummary.objects.get_or_create(
            date=date, plaza_id=plaza_id, lane_id=lane_id, vehicle_type=vehicle_type,
            defaults={'entries': 0, 'exits': 0, 'revenue': 0},
        )
        DailySummary.objects.filter(pk=obj.pk).update(entries=F('entries') + 1)
    except Exception as exc:
        logger.warning("daily_summary entry update failed: %s", exc)


def _inc_summary_exit(plaza_id, lane_id, vehicle_type, date, charge):
    """Atomically increment exit count and revenue in daily_summaries."""
    try:
        obj, _ = DailySummary.objects.get_or_create(
            date=date, plaza_id=plaza_id, lane_id=lane_id, vehicle_type=vehicle_type,
            defaults={'entries': 0, 'exits': 0, 'revenue': 0},
        )
        DailySummary.objects.filter(pk=obj.pk).update(
            exits=F('exits') + 1,
            revenue=F('revenue') + charge,
        )
    except Exception as exc:
        logger.warning("daily_summary exit update failed: %s", exc)


# ── Master reads (no master WRITES from the gate path) ────────────────────────
#
# The gate writes to the LOCAL database only. Everything reaching master goes
# through the separate sync service (apps/tolls/sync/), so a master outage can
# never close a lane and the gate carries no replication logic.
#
# The two helpers below are READS, kept because correctness needs them: an exit
# must be able to find an entry made moments ago at another plaza, and an entry
# must not be refused by a local row that master already knows is closed.

def _refresh_trips_from_master(trip_ids) -> dict:
    """Overwrite local trip rows with master's authoritative values.

    Returns {trip_id: master_status} for every id master actually has.

    Writes updated_at explicitly from master's value (raw SQL, so TollTrip's
    auto_now does not clobber it). That keeps local and master byte-identical on
    these columns and means correctness never depends on pull_closed_trips
    winning its `local.updated_at < master.updated_at` race afterwards.
    """
    from django.db import connection, connections

    trip_ids = [str(t) for t in trip_ids]
    if not trip_ids:
        return {}

    with connections['master_pg'].cursor() as mcur:
        mcur.execute("""
            SELECT id, exit_plaza_id, exit_lane_id, exit_time, charge_amount,
                   balance_before, balance_after, status, updated_at
            FROM toll_trips WHERE id = ANY(%s)
        """, [trip_ids])
        rows = mcur.fetchall()

    statuses = {}
    with connection.cursor() as lcur:
        for row in rows:
            lcur.execute("""
                UPDATE toll_trips SET
                    exit_plaza_id  = %s, exit_lane_id   = %s, exit_time     = %s,
                    charge_amount  = %s, balance_before = %s, balance_after = %s,
                    status         = %s, updated_at     = %s
                WHERE id = %s
            """, (row[1], row[2], row[3], row[4], row[5],
                  row[6], row[7], row[8], row[0]))
            statuses[str(row[0])] = row[7]
    return statuses


def _reconcile_local_active_trips(trip_ids) -> list:
    """Given local trips believed ACTIVE, return those master agrees are active.

    Any that master reports as closed are closed locally too. This exists so a
    stale local row cannot falsely reject a legitimate entry: pull_closed_trips
    only runs every 30s, and a vehicle can exit one plaza and re-enter well
    inside that window. Master is authoritative, so ask it directly. If master
    is unreachable the call fails closed (keeps the local answer) — it never
    blocks the lane on master being up.

    A trip missing from master entirely is treated as STILL ACTIVE and reported.
    It normally means the push pass has not replicated this entry yet, which is
    expected right after an entry; auto-clearing it could open the door to an
    untolled second trip, so a human decides.
    """
    trip_ids = [str(t) for t in trip_ids]
    if not trip_ids:
        return []

    try:
        statuses = _refresh_trips_from_master(trip_ids)
    except Exception as exc:
        # Can't verify — keep the existing conservative behaviour and reject.
        logger.warning("Could not verify active trips against master: %s", exc)
        return trip_ids

    still_active = []
    for tid in trip_ids:
        status = statuses.get(tid)
        if status is None:
            logger.error(
                "Trip %s is active locally but absent on master — not auto-clearing",
                tid,
            )
            still_active.append(tid)
        elif status == TripStatus.ACTIVE:
            still_active.append(tid)
        else:
            logger.info("Closed stale local trip %s as '%s' per master", tid, status)

    return still_active


# ── Entry ─────────────────────────────────────────────────────────────────────

class EntryService:
    @staticmethod
    def process_entry(tag_serial: str, plaza_id: str, lane_id: str = None) -> dict:
        logger.info("Entry — tag: %s plaza: %s", tag_serial, plaza_id)

        with db_transaction.atomic():
            # 1. Verify tag + vehicle (single query via select_related)
            #    Match on the chip TID — the reader passes the scanned TID here.
            try:
                tag = Tag.objects.select_related('vehicle').get(tid=tag_serial)
            except Tag.DoesNotExist:
                return {'success': False, 'reason': 'Tag not found'}

            if not tag.is_valid:
                if tag.vehicle_id is None:
                    return {'success': False, 'reason': 'Tag not assigned to any vehicle'}
                if tag.status != TagStatus.ACTIVE:
                    return {'success': False, 'reason': f'Tag is {tag.status}'}
                return {'success': False, 'reason': 'Tag expired'}

            vehicle = tag.vehicle
            if vehicle.status != 'active':
                return {'success': False, 'reason': f'Vehicle is {vehicle.status}'}

            # 2. Lock account and check minimum balance
            try:
                account = Account.objects.select_for_update().get(vehicle=vehicle)
            except Account.DoesNotExist:
                return {'success': False, 'reason': 'No account found for this vehicle'}

            if account.balance < MINIMUM_BALANCE:
                return {
                    'success': False,
                    'reason': 'Insufficient balance',
                    'current_balance': str(account.balance),
                    'minimum_required': str(MINIMUM_BALANCE),
                }

            # 3. Prevent duplicate active trip.
            #    TEST CONVENIENCE: when settings.ENTRY_AUTO_RESET_ACTIVE_TRIP is on
            #    (dev/local only — NOT in production), auto-clear any existing active
            #    trip so the same tag can re-enter repeatedly without a manual reset.
            active_trips = TollTrip.objects.filter(vehicle=vehicle, status=TripStatus.ACTIVE)
            if active_trips.exists():
                if getattr(settings, 'ENTRY_AUTO_RESET_ACTIVE_TRIP', False):
                    cleared = active_trips.count()
                    active_trips.delete()
                    logger.warning(
                        "[TEST] Auto-reset %d active trip(s) for %s before new entry",
                        cleared, vehicle.plate_number,
                    )
                else:
                    # The local row may be stale — a trip completed at another
                    # plaza stays 'active' here until pull_closed_trips catches
                    # up. Confirm with master before turning a paying customer
                    # away; _reconcile_local_active_trips closes stale rows.
                    if _reconcile_local_active_trips(
                        active_trips.values_list('id', flat=True)
                    ):
                        return {
                            'success': False,
                            'reason': 'Vehicle already has an active trip',
                        }

            # 4. Resolve lane (optional — failure is non-fatal)
            lane = None
            if lane_id:
                try:
                    lane = TollLane.objects.get(id=lane_id, is_active=True)
                except TollLane.DoesNotExist:
                    pass

            # 5. Create trip record — committed locally when this block exits.
            trip = TollTrip.objects.create(
                vehicle=vehicle,
                tag=tag,
                account=account,
                entry_plaza_id=plaza_id,
                entry_lane=lane,
                status=TripStatus.ACTIVE,
            )

        # The trip is committed locally. The sync service's push pass replicates
        # it to master (entry booths run push for exactly this reason), so a
        # master outage delays reporting but never blocks the barrier.

        # Non-critical background updates
        _bg(_update_last_scanned, tag.id)
        _bg(_inc_summary_entry, plaza_id, lane.id if lane else None, vehicle.vehicle_type, trip.entry_time.date())

        logger.info("Entry OK — trip: %s vehicle: %s", trip.id, vehicle.plate_number)
        return {
            'success': True,
            'trip_id': str(trip.id),
            'vehicle': vehicle.plate_number,
            'vehicle_type': vehicle.vehicle_type,
            'current_balance': str(account.balance),
            'entry_time': trip.entry_time.isoformat(),
        }


# ── Exit helpers ──────────────────────────────────────────────────────────────

def _find_active_trip(vehicle):
    """
    Find active trip for vehicle.

    Lookup order:
      1. Local DB (default connection) — fast, covers the vast majority of
         cases. The sync service's pull pass mirrors master's open trips into
         every exit booth's local DB each cycle.
      2. Master DB (explicit master_pg) — read-only fallback for the short-hop
         case where a vehicle exits before the next pull cycle lands. This is a
         READ; the gate never writes to master.
    """
    from django.db import connections

    trip = TollTrip.objects.select_related('entry_plaza', 'vehicle').filter(
        vehicle=vehicle, status=TripStatus.ACTIVE
    ).first()
    if trip:
        return trip

    try:
        with connections['master_pg'].cursor() as mcur:
            mcur.execute("""
                SELECT id, vehicle_id, tag_id, account_id, entry_plaza_id,
                       entry_lane_id, entry_time, exit_plaza_id, exit_lane_id,
                       exit_time, charge_amount, balance_before, balance_after,
                       status, created_at, updated_at
                FROM toll_trips
                WHERE vehicle_id = %s AND status = 'active'
                LIMIT 1
            """, [str(vehicle.id)])
            row = mcur.fetchone()
            if row:
                # Pull trip into local DB so ExitService can lock it normally
                from django.db import connection
                with connection.cursor() as lcur:
                    lcur.execute("""
                        INSERT INTO toll_trips (
                            id, vehicle_id, tag_id, account_id, entry_plaza_id,
                            entry_lane_id, entry_time, exit_plaza_id, exit_lane_id,
                            exit_time, charge_amount, balance_before, balance_after,
                            status, created_at, updated_at)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (id) DO NOTHING
                    """, row)
                logger.info("Master fallback — pulled trip %s to local", row[0])
                return TollTrip.objects.select_related(
                    'entry_plaza', 'vehicle'
                ).get(id=row[0])
    except Exception as exc:
        logger.warning("Master fallback trip lookup failed: %s", exc)

    return None


# ── Exit ──────────────────────────────────────────────────────────────────────

class ExitService:
    @staticmethod
    def process_exit(tag_serial: str, exit_plaza_id: str, lane_id: str = None) -> dict:
        logger.info("Exit — tag: %s plaza: %s", tag_serial, exit_plaza_id)

        with db_transaction.atomic():
            # 1. Verify tag + vehicle — match on the chip TID (scanned value)
            try:
                tag = Tag.objects.select_related('vehicle').get(tid=tag_serial)
            except Tag.DoesNotExist:
                return {'success': False, 'reason': 'Tag not found'}

            # 2. Find active trip (local first, master fallback for cross-plaza)
            trip = _find_active_trip(tag.vehicle)
            if not trip:
                return {'success': False, 'reason': 'No active trip found for this vehicle'}

            # Re-fetch with lock now that we know the trip exists locally
            try:
                trip = TollTrip.objects.select_for_update().select_related(
                    'entry_plaza', 'vehicle'
                ).get(id=trip.id, status=TripStatus.ACTIVE)
            except TollTrip.DoesNotExist:
                return {'success': False, 'reason': 'Trip was already processed'}

            # 3. Rate lookup — served from cache on warm requests
            rate = _cached_rate(
                str(trip.entry_plaza_id), exit_plaza_id, trip.vehicle.vehicle_type
            )
            if rate is None:
                logger.error(
                    "No toll rate: %s→%s %s",
                    trip.entry_plaza_id, exit_plaza_id, trip.vehicle.vehicle_type,
                )
                return {'success': False, 'reason': 'Toll rate not configured for this route'}

            charge = Decimal(str(rate)).quantize(Decimal('0.01'))

            # 4. Lock account and check balance
            account = Account.objects.select_for_update().get(id=trip.account_id)
            if account.balance < charge:
                return {
                    'success': False,
                    'reason': 'Insufficient balance at exit',
                    'charge': str(charge),
                    'current_balance': str(account.balance),
                }

            # 5. Deduct balance
            now = timezone.now()
            balance_before = account.balance
            account.balance -= charge
            account.save(update_fields=['balance', 'balance_updated_at'])

            # 6. Resolve lane (optional)
            lane = None
            if lane_id:
                try:
                    lane = TollLane.objects.get(id=lane_id, is_active=True)
                except TollLane.DoesNotExist:
                    pass

            # 7. Close trip
            trip.exit_plaza_id = exit_plaza_id
            trip.exit_lane = lane
            trip.exit_time = now
            trip.charge_amount = charge
            trip.balance_before = balance_before
            trip.balance_after = account.balance
            trip.status = TripStatus.COMPLETED
            trip.save()

            # 8. Audit transaction record — committed locally when this block exits.
            txn = Transaction.objects.create(
                account=account,
                toll_lane=lane,
                toll_trip=trip,
                tag_serial=tag_serial,
                transaction_type=TransactionType.TOLL_DEDUCTION,
                amount=charge,
                balance_before=balance_before,
                balance_after=account.balance,
                status=TransactionStatus.SUCCESS,
            )

        # The exit, balance deduction and audit transaction are all committed
        # locally in the atomic block above. The sync service's push pass sends
        # the trip, the balance and the transaction to master, and refuses to
        # overwrite an exit master has already recorded (see push_toll_trips).

        # Non-critical background updates
        _bg(_update_last_scanned, tag.id)
        _bg(_inc_summary_exit, exit_plaza_id, lane.id if lane else None, trip.vehicle.vehicle_type, now.date(), charge)

        logger.info("Exit OK — trip: %s charge: %s balance: %s", trip.id, charge, account.balance)
        return {
            'success': True,
            'trip_id': str(trip.id),
            'vehicle': trip.vehicle.plate_number,
            'entry_plaza': trip.entry_plaza.name,
            'exit_plaza_id': exit_plaza_id,
            'charge': str(charge),
            'balance_remaining': str(account.balance),
            'entry_time': trip.entry_time.isoformat(),
            'exit_time': now.isoformat(),
        }

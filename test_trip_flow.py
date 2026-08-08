"""
End-to-end trip flow test: entry at one plaza, exit at another, sync, re-entry.

Run from mtag_backend/ on the BOOTH machine (.13), with .env pointed at the
booth test DB locally and the master test DB remotely:

    python manage.py shell < ../test_trip_flow.py

Requires SYNC_AGENT_ENABLED=False in .env, otherwise the background agent syncs
underneath the test and the results are nondeterministic.

Covers, in order:
  1. entry at KPT writes locally AND to master (synchronous dual-write)
  2. exit at EBM charges the KPT->EBM fare and closes the trip on both
  3. a stale local 'active' row is flipped to completed by pull_closed_trips
  4. re-entry then succeeds  <- the bug that blocked every vehicle's 2nd trip
  5. a duplicate exit is refused and the balance is NOT deducted twice
"""
from decimal import Decimal

from django.db import connection, connections

from apps.accounts.models import Account
from apps.tolls.models import Plaza, TollTrip, TripStatus
from apps.tolls.services import EntryService, ExitService
from apps.tolls.sync.connections import get_local_conn, get_master_conn
from apps.tolls.sync.trip_sync import sync_trip_lifecycle
from apps.vehicles.models import Tag

FAILURES = []


def check(label, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}: {label}{f' — {detail}' if detail else ''}")
    if not ok:
        FAILURES.append(label)


def master_trip(trip_id):
    """Read a trip straight from master, bypassing all local state."""
    with connections['master_pg'].cursor() as cur:
        cur.execute(
            "SELECT status, exit_plaza_id, charge_amount FROM toll_trips WHERE id = %s",
            [str(trip_id)],
        )
        return cur.fetchone()


def run_sync():
    mconn, lconn = get_master_conn(), get_local_conn()
    try:
        with mconn, lconn:
            with mconn.cursor() as mc, lconn.cursor() as lc:
                return sync_trip_lifecycle(mc, lc)
    finally:
        mconn.close()
        lconn.close()


print("\n=== Environment (confirm these are the TEST databases) ===")
from django.conf import settings
_d, _m = settings.DATABASES['default'], settings.DATABASES['master_pg']
print(f"  local  : {_d['NAME']} @ {_d['HOST'] or 'localhost'}")
print(f"  master : {_m['NAME']} @ {_m['HOST']}")
print(f"  online-only={getattr(settings, 'ONLINE_ONLY_MODE', None)} "
      f"sync-agent={getattr(settings, 'SYNC_AGENT_ENABLED', None)}")

print("\n=== 0. Fixtures ===")
from apps.tolls.models import TollRate
from apps.vehicles.models import Vehicle

print(f"  counts: plazas={Plaza.objects.count()} rates={TollRate.objects.count()} "
      f"vehicles={Vehicle.objects.count()} tags={Tag.objects.count()} "
      f"accounts={Account.objects.count()}")

if Plaza.objects.count() == 0:
    raise SystemExit(
        "  ABORT: no plazas in the local DB. Run step 5 (run_pull) first, or "
        "'python manage.py seed_data' if this IS the master DB."
    )

kpt = Plaza.objects.get(plaza_id=1)
ebm = Plaza.objects.get(plaza_id=2)
print(f"  entry plaza={kpt.plaza_id} ({kpt.name})   exit plaza={ebm.plaza_id} ({ebm.name})")

# Find a usable tag: needs a vehicle AND an account, else entry can't proceed.
# seed_data only creates the tag/account inside `if created:` for the vehicle,
# so a re-run against a DB that already had KHI-1001 leaves no tag at all.
tag = (Tag.objects.select_related('vehicle')
       .filter(vehicle__isnull=False, vehicle__account__isnull=False)
       .first())

MASTER_FIXTURE_HINT = """
  Create it ON MASTER (not here) — entry dual-writes a trip FK'd to vehicle_id
  and account_id, so those rows must exist on master or the write is an FK
  violation and the entry is rejected. Point .env at the master DB, run:

    python manage.py shell -c "
    from datetime import date
    from django.contrib.auth import get_user_model
    from apps.vehicles.models import Vehicle, Tag
    from apps.accounts.models import Account
    U = get_user_model()
    u = U.objects.first() or U.objects.create(phone='03111111111', full_name='Flow Test', user_role='operator')
    v,_ = Vehicle.objects.get_or_create(plate_number='FLOWTEST-1', defaults={'vehicle_type':'car','owner':u})
    Account.objects.get_or_create(vehicle=v, defaults={'user':u,'balance':'5000.00'})
    t,_ = Tag.objects.get_or_create(tag_serial='FLOWTEST01', defaults={'vehicle':v,'expiry_date':date(2099,12,31)})
    t.vehicle=v; t.tid='E28011FLOWTEST01'[:24]; t.save()
    print('master fixture ready:', t.tag_serial, t.tid, v.plate_number)"

  Then point .env back at the booth DB, re-run run_pull, and re-run this test.
"""

if tag is None:
    raise SystemExit(
        "  ABORT: no tag with both a vehicle and an account exists locally.\n"
        "  (seed_data only creates the tag/account inside `if created:` for the\n"
        "  vehicle, so it makes none if the plate already existed.)"
        + MASTER_FIXTURE_HINT
    )

# The tag exists locally, but entry's dual-write needs its vehicle AND account on
# master too. Check now — otherwise stage 1 fails with an opaque FK error.
with connections['master_pg'].cursor() as cur:
    cur.execute("SELECT 1 FROM vehicles WHERE id = %s", [str(tag.vehicle_id)])
    v_on_master = cur.fetchone() is not None
    cur.execute("SELECT 1 FROM accounts WHERE vehicle_id = %s", [str(tag.vehicle_id)])
    a_on_master = cur.fetchone() is not None
if not (v_on_master and a_on_master):
    raise SystemExit(
        f"  ABORT: tag {tag.tag_serial} exists locally but master is missing "
        f"{'its vehicle ' if not v_on_master else ''}"
        f"{'its account' if not a_on_master else ''}.\n"
        "  Entry would be rejected by the master dual-write (FK violation)."
        + MASTER_FIXTURE_HINT
    )
print("  master has the vehicle + account (dual-write will not FK-fail)")

# Both EntryService and ExitService look tags up by `tid` exclusively, and
# seed_data never sets one — so ensure it exists before any scan is simulated.
if not tag.tid:
    tag.tid = ('E28011' + tag.tag_serial)[:24]
    tag.save(update_fields=['tid'])

tag.refresh_from_db()
print(f"  tag={tag.tag_serial} tid={tag.tid} vehicle={tag.vehicle.plate_number} "
      f"status={tag.status} valid={tag.is_valid}")

rate = TollRate.objects.filter(
    entry_plaza=kpt, exit_plaza=ebm, vehicle_type=tag.vehicle.vehicle_type
).first()
if rate is None:
    raise SystemExit(
        f"  ABORT: no toll rate for plaza {kpt.plaza_id} -> {ebm.plaza_id} "
        f"({tag.vehicle.vehicle_type}). Exit would fail with 'Toll rate not "
        f"configured'. Seed rates on master and re-run run_pull."
    )
print(f"  rate {kpt.plaza_id}->{ebm.plaza_id} ({tag.vehicle.vehicle_type}) = {rate.rate}")

# Clean slate so a re-run is deterministic. Must clear BOTH sides: a leftover
# active trip on master would make _reconcile_local_active_trips reject stage 1's
# entry ("Vehicle already has an active trip") even with the local row gone.
# Transaction.toll_trip is SET_NULL, so deleting trips never cascades to money rows.
TollTrip.objects.filter(vehicle=tag.vehicle).delete()
with connections['master_pg'].cursor() as cur:
    cur.execute("DELETE FROM toll_trips WHERE vehicle_id = %s", [str(tag.vehicle_id)])
    print(f"  cleared {cur.rowcount} leftover trip(s) on master")

account = Account.objects.get(vehicle=tag.vehicle)
account.balance = Decimal('5000.00')
account.save(update_fields=['balance', 'balance_updated_at'])
start_balance = account.balance
print(f"  balance reset to {start_balance}")


print("\n=== 1. Entry at KPT ===")
res = EntryService.process_entry(tag.tid, str(kpt.id))
print(f"  {res}")
check("entry accepted", res.get('success'), res.get('reason', ''))
trip_id = res.get('trip_id')

if trip_id:
    m = master_trip(trip_id)
    check("master received the trip synchronously", m is not None and m[0] == 'active',
          f"master row={m}")


print("\n=== 2. Exit at EBM (cross-plaza) ===")
res = ExitService.process_exit(tag.tid, str(ebm.id))
print(f"  {res}")
check("exit accepted", res.get('success'), res.get('reason', ''))
charge = Decimal(res['charge']) if res.get('charge') else None
check("fare charged is non-zero", charge and charge > 0, f"charge={charge}")

account.refresh_from_db()
check("balance deducted exactly once",
      account.balance == start_balance - (charge or 0),
      f"{start_balance} -> {account.balance}")

m = master_trip(trip_id)
check("master shows trip completed", m and m[0] == 'completed', f"master row={m}")


print("\n=== 3. Stale local 'active' row is repaired by sync ===")
# Simulate the real bug: another booth pulled this trip while it was open and
# never learned it closed. updated_at is forced OLD so pull_closed_trips'
# `local.updated_at < master.updated_at` guard fires.
with connection.cursor() as cur:
    cur.execute("""
        UPDATE toll_trips
           SET status='active', exit_plaza_id=NULL, exit_time=NULL,
               charge_amount=NULL, updated_at='2000-01-01T00:00:00+00:00'
         WHERE id = %s
    """, [trip_id])
print("  forced local row back to 'active' (simulating a stale booth copy)")

result = run_sync()
print(f"  sync_trip_lifecycle -> {result}")
local_status = TollTrip.objects.get(id=trip_id).status
check("stale local row flipped to completed", local_status == TripStatus.COMPLETED,
      f"local status={local_status}")


print("\n=== 4. Re-entry now works (the bug that blocked 2nd trips) ===")
res = EntryService.process_entry(tag.tid, str(kpt.id))
print(f"  {res}")
check("re-entry accepted after previous trip closed", res.get('success'),
      res.get('reason', ''))
trip2 = res.get('trip_id')


print("\n=== 5. Duplicate exit must NOT double-charge ===")
if trip2:
    # Close trip2 properly first.
    r = ExitService.process_exit(tag.tid, str(ebm.id))
    check("second trip exits normally", r.get('success'), r.get('reason', ''))
    account.refresh_from_db()
    balance_after_paid = account.balance

    # Now force the local row back to active while master keeps it completed —
    # exactly the state that used to permit a second charge.
    with connection.cursor() as cur:
        cur.execute("UPDATE toll_trips SET status='active' WHERE id = %s", [trip2])

    dup = ExitService.process_exit(tag.tid, str(ebm.id))
    print(f"  duplicate attempt -> {dup}")
    check("duplicate exit refused", not dup.get('success'), str(dup))
    check("refusal reason is 'already processed', not a master-outage error",
          dup.get('reason') == 'Trip was already processed', dup.get('reason'))

    account.refresh_from_db()
    check("balance unchanged by the duplicate",
          account.balance == balance_after_paid,
          f"{balance_after_paid} -> {account.balance}")

    m = master_trip(trip2)
    check("master still holds the original exit", m and m[0] == 'completed',
          f"master row={m}")


print("\n" + "=" * 60)
if FAILURES:
    print(f"{len(FAILURES)} CHECK(S) FAILED:")
    for f in FAILURES:
        print(f"  - {f}")
else:
    print("ALL CHECKS PASSED")
print("=" * 60)

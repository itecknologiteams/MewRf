"""
Trip lifecycle sync — the whole Entry → Master → Exit pipeline, in one place.

    Entry booth                 Master                  Exit booth
    ───────────                 ──────                  ──────────
 1. trip created    ──sync──▶   open trip
    status=active               (source of truth)
 2.                             open trip   ──sync──▶   local copy of open trip
 3.                                                     reads it, charges the
                                                        entry→exit fare, closes it
 4.                 ◀──sync──   closed trip ──sync──▶   every other booth learns
                                                        the trip is closed

Who does what:

  Step 1  services.py::_dual_write_entry_to_master — SYNCHRONOUS. Master has the
          trip before the barrier opens, so an exit can never be processed
          against a trip master has never heard of. If master refuses the write,
          the entry itself is rejected.

  Step 2  pull_active_trips() below. Full refresh every cycle, no timestamp
          filter, so a booth that missed cycles still catches up completely.

  Step 3  services.py::ExitService. _find_active_trip reads the local copy, and
          falls back to a direct master read when a vehicle exits faster than
          one sync interval (short hops like KPT→EBM).

  Step 4  pull_closed_trips() below. Without this, a completed trip drops out of
          step 2's `status='active'` query and the other booths keep their copy
          as active forever — which blocks the vehicle's next entry and lets
          another lane try to charge an already-paid trip.

Direction: booths always dial master, never the reverse. Adding a booth needs no
master-side configuration and no inbound firewall rule on the booth. Master
holds no per-booth state, so it cannot become a propagation bottleneck.
"""
import logging
from datetime import datetime, timezone

import psycopg2.extras

log = logging.getLogger('apps.tolls.sync.trips')

# Watermark key in the sync_log table for the closed-trip pass.
WATERMARK = 'closed_trips'

# Shared column list — declared once so the two queries below can never drift
# apart. Order matters: it is reused verbatim by both SELECT and INSERT.
_TRIP_COLS = """id, vehicle_id, tag_id, account_id, entry_plaza_id,
               entry_lane_id, entry_time, exit_plaza_id, exit_lane_id,
               exit_time, charge_amount, balance_before, balance_after,
               status, created_at, updated_at"""

# Applied on conflict for both passes. The updated_at guard stops an older row
# from overwriting a newer one, whichever direction it arrives from.
_UPSERT_TAIL = """
        ON CONFLICT (id) DO UPDATE SET
            status         = EXCLUDED.status,
            exit_plaza_id  = EXCLUDED.exit_plaza_id,
            exit_lane_id   = EXCLUDED.exit_lane_id,
            exit_time      = EXCLUDED.exit_time,
            charge_amount  = EXCLUDED.charge_amount,
            balance_before = EXCLUDED.balance_before,
            balance_after  = EXCLUDED.balance_after,
            updated_at     = EXCLUDED.updated_at
        WHERE toll_trips.updated_at < EXCLUDED.updated_at
"""


def _now():
    return datetime.now(timezone.utc)


def _upsert_trips(local_cur, rows) -> int:
    psycopg2.extras.execute_values(
        local_cur,
        f"INSERT INTO toll_trips ({_TRIP_COLS}) VALUES %s {_UPSERT_TAIL}",
        rows,
    )
    return len(rows)


def get_watermark(local_cur) -> datetime:
    """Last successful closed-trip pull time for this booth."""
    local_cur.execute(
        "SELECT last_pull_at FROM sync_log WHERE table_name = %s", (WATERMARK,)
    )
    row = local_cur.fetchone()
    if row and row[0]:
        return row[0]
    return datetime(2000, 1, 1, tzinfo=timezone.utc)


def set_watermark(local_cur, ts: datetime) -> None:
    local_cur.execute("""
        INSERT INTO sync_log (table_name, last_pull_at)
        VALUES (%s, %s)
        ON CONFLICT (table_name) DO UPDATE SET last_pull_at = EXCLUDED.last_pull_at
    """, (WATERMARK, ts))


# ── Step 2: master's open trips → this booth ──────────────────────────────────

def pull_active_trips(master_cur, local_cur) -> int:
    """Full refresh of every open trip. No timestamp filter on purpose: a booth
    that missed cycles (or was reimaged) still ends up with the complete set."""
    master_cur.execute(
        f"SELECT {_TRIP_COLS} FROM toll_trips WHERE status = 'active'"
    )
    rows = master_cur.fetchall()
    return _upsert_trips(local_cur, rows) if rows else 0


# ── Step 4: trips closed elsewhere → this booth ───────────────────────────────

def pull_closed_trips(master_cur, local_cur, since: datetime) -> int:
    """Pull trips that are no longer active, so this booth learns they closed.

    Timestamp-driven on updated_at (indexed — see TollTrip.Meta.indexes) so each
    cycle only carries what actually changed, rather than the whole history.
    """
    master_cur.execute(
        f"SELECT {_TRIP_COLS} FROM toll_trips "
        "WHERE status <> 'active' AND updated_at > %s",
        (since,),
    )
    rows = master_cur.fetchall()
    return _upsert_trips(local_cur, rows) if rows else 0


# ── The pipeline ──────────────────────────────────────────────────────────────

def sync_trip_lifecycle(master_cur, local_cur, include_open: bool = True) -> dict:
    """Run the master→booth trip passes. Returns {'active': n, 'closed': n}.

    `include_open=False` (entry booths) skips the open-trip pass: an entry booth
    never charges against another plaza's open trip, so copying them in is pure
    overhead. The closed pass always runs — both modes need it, or a completed
    trip sits at 'active' locally forever and blocks that vehicle's next entry.

    Order is load-bearing when both run: the open pass re-inserts rows this booth
    may still hold as stale-active, and the closed pass is what flips them to
    completed. Reversed, the stale rows would survive a full cycle.
    """
    active = pull_active_trips(master_cur, local_cur) if include_open else 0

    since = get_watermark(local_cur)
    closed = pull_closed_trips(master_cur, local_cur, since)
    if closed:
        set_watermark(local_cur, _now())

    return {'active': active, 'closed': closed}

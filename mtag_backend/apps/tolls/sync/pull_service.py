"""
PULL service: master → booth. The other half of the sync service; see
push_service.py. Never called from the RFID/gate path — the gate only reads its
local database, and this process is what keeps that database current.

Two independent passes, because the two booth modes need different things:

  pull_reference()  — plazas, toll_lanes, toll_rates, tags, users, vehicles,
                      accounts. Master owns all of it. BOTH modes need this: an
                      entry booth cannot validate a tag or check a balance
                      without it, and an exit booth cannot price a fare.

  pull_trips()      — open trips (full refresh) + trips closed elsewhere
                      (timestamp-based). Only an EXIT booth needs open trips, to
                      charge against them. Closed trips matter to both modes:
                      without them a completed trip stays 'active' locally
                      forever and blocks the vehicle's next entry.

Strategy: ON CONFLICT DO UPDATE so local mirrors master. Timestamp guards stop
an older row overwriting a newer one in either direction.
"""
import logging
from datetime import datetime, timezone

import psycopg2.extras

from apps.tolls.sync.connections import get_local_conn, get_master_conn
from apps.tolls.sync.trip_sync import sync_trip_lifecycle

log = logging.getLogger('apps.tolls.sync.pull')


def _now():
    return datetime.now(timezone.utc)


def _get_last_pull(local_cur, table: str):
    local_cur.execute(
        "SELECT last_pull_at FROM sync_log WHERE table_name = %s",
        (table,)
    )
    row = local_cur.fetchone()
    if row and row[0]:
        return row[0]
    return datetime(2000, 1, 1, tzinfo=timezone.utc)


def _set_last_pull(local_cur, table: str, ts: datetime):
    local_cur.execute("""
        INSERT INTO sync_log (table_name, last_pull_at)
        VALUES (%s, %s)
        ON CONFLICT (table_name) DO UPDATE SET last_pull_at = EXCLUDED.last_pull_at
    """, (table, ts))



def _resync_sequence(cur, table: str, column: str = 'id') -> None:
    """Realign a table's id sequence after inserting rows with explicit ids.

    The sync upserts rows using the ids the other side assigned, which bypasses
    the sequence entirely — it stays where it was while the data moves ahead.
    The next locally-created row then reuses a taken id and the INSERT dies with
    "duplicate key value violates unique constraint <table>_pkey". Seen in the
    wild on `users` before every table had an integer key.

    Since primary keys became integers this applies to EVERY synced table, not
    just users — which is why _resync_all() below runs after each pass.
    """
    cur.execute(
        "SELECT setval(pg_get_serial_sequence(%s, %s), "
        "       GREATEST(COALESCE((SELECT MAX(" + column + ") FROM " + table + "), 1), 1))",
        (f"public.{table}", column),
    )


# Every table this service moves rows for. All have integer primary keys now, so
# all of them need their sequence realigned after an upsert with explicit ids.
SYNCED_TABLES = (
    'users', 'vehicles', 'tags', 'tag_assignments', 'accounts',
    'plazas', 'toll_lanes', 'toll_rates', 'vehicle_categories',
    'fare_matrix', 'toll_trips', 'transactions',
)


def _resync_all(cur) -> None:
    """Realign every synced table's sequence. Cheap (one setval each) and safe
    to run every cycle — setval to MAX(id) is idempotent."""
    for table in SYNCED_TABLES:
        try:
            _resync_sequence(cur, table)
        except Exception:
            # A table may not exist yet on a partially-migrated peer. Never let
            # sequence maintenance abort a sync cycle.
            log.debug("sequence resync skipped for %s", table, exc_info=True)


# ── Full-refresh tables (no timestamp columns) ────────────────────────────────

def pull_plazas(master_cur, local_cur) -> int:
    master_cur.execute(
        "SELECT id, plaza_id, name, latitude, longitude, is_active FROM plazas"
    )
    rows = master_cur.fetchall()
    if not rows:
        return 0
    psycopg2.extras.execute_values(local_cur, """
        INSERT INTO plazas (id, plaza_id, name, latitude, longitude, is_active)
        VALUES %s
        ON CONFLICT (id) DO UPDATE SET
            plaza_id  = EXCLUDED.plaza_id,
            name      = EXCLUDED.name,
            latitude  = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            is_active = EXCLUDED.is_active
    """, rows)
    return len(rows)


def pull_toll_lanes(master_cur, local_cur) -> int:
    master_cur.execute(
        "SELECT id, plaza_id, lane_number, is_active FROM toll_lanes"
    )
    rows = master_cur.fetchall()
    if not rows:
        return 0
    psycopg2.extras.execute_values(local_cur, """
        INSERT INTO toll_lanes (id, plaza_id, lane_number, is_active)
        VALUES %s
        ON CONFLICT (id) DO UPDATE SET
            is_active   = EXCLUDED.is_active,
            lane_number = EXCLUDED.lane_number
    """, rows)
    return len(rows)


def pull_toll_rates(master_cur, local_cur) -> int:
    master_cur.execute("""
        SELECT id, entry_plaza_id, exit_plaza_id, vehicle_type,
               rate, peak_multiplier, effective_from
        FROM toll_rates
    """)
    rows = master_cur.fetchall()
    if not rows:
        return 0
    psycopg2.extras.execute_values(local_cur, """
        INSERT INTO toll_rates (id, entry_plaza_id, exit_plaza_id,
               vehicle_type, rate, peak_multiplier, effective_from)
        VALUES %s
        ON CONFLICT (id) DO UPDATE SET
            rate             = EXCLUDED.rate,
            peak_multiplier  = EXCLUDED.peak_multiplier
    """, rows)
    return len(rows)


def pull_tag_assignments(master_cur, local_cur) -> int:
    """Tag installation history (vehicles.TagAssignment). Full refresh — small,
    append-mostly, and a booth needs the whole chain to answer 'where was this
    tag before'. Runs AFTER tags/vehicles: every row FKs both."""
    master_cur.execute("SELECT id, tag_id, tag_serial, vehicle_id, plate_number, assigned_at, assigned_by_id, removed_at, removed_reason, notes, created_at, updated_at FROM tag_assignments")
    rows = master_cur.fetchall()
    if not rows:
        return 0
    psycopg2.extras.execute_values(local_cur, """
        INSERT INTO tag_assignments (id, tag_id, tag_serial, vehicle_id, plate_number, assigned_at, assigned_by_id, removed_at, removed_reason, notes, created_at, updated_at)
        VALUES %s
        ON CONFLICT (id) DO UPDATE SET
            tag_id         = EXCLUDED.tag_id,
            vehicle_id     = EXCLUDED.vehicle_id,
            plate_number   = EXCLUDED.plate_number,
            removed_at     = EXCLUDED.removed_at,
            removed_reason = EXCLUDED.removed_reason,
            notes          = EXCLUDED.notes,
            updated_at     = EXCLUDED.updated_at
    """, rows)
    return len(rows)


def pull_vehicle_categories(master_cur, local_cur) -> int:
    """Full refresh — tiny, master-owned billing categories."""
    master_cur.execute("""
        SELECT id, category_index, code, name, description,
               is_active, created_at, updated_at
        FROM vehicle_categories
    """)
    rows = master_cur.fetchall()
    if not rows:
        return 0
    psycopg2.extras.execute_values(local_cur, """
        INSERT INTO vehicle_categories (id, category_index, code, name,
               description, is_active, created_at, updated_at)
        VALUES %s
        ON CONFLICT (id) DO UPDATE SET
            category_index = EXCLUDED.category_index,
            code           = EXCLUDED.code,
            name           = EXCLUDED.name,
            description    = EXCLUDED.description,
            is_active      = EXCLUDED.is_active,
            updated_at     = EXCLUDED.updated_at
    """, rows)
    return len(rows)


def pull_fare_matrix(master_cur, local_cur) -> int:
    """Full refresh of the fare matrix.

    MUST run after pull_plazas and pull_vehicle_categories — every row FKs a
    plaza and a category, so pulling it first would fail on the foreign keys.
    Full refresh rather than timestamp-based: the table is small (plazas^2 x
    categories) and a booth pricing a trip from a half-synced matrix would
    under-bill, so it is always brought over whole.
    """
    master_cur.execute("""
        SELECT id, from_plaza_id, to_plaza_id, category_index,
               fare, created_at, updated_at
        FROM fare_matrix
    """)
    rows = master_cur.fetchall()
    if not rows:
        return 0
    psycopg2.extras.execute_values(local_cur, """
        INSERT INTO fare_matrix (id, from_plaza_id, to_plaza_id,
               category_index, fare, created_at, updated_at)
        VALUES %s
        ON CONFLICT (id) DO UPDATE SET
            from_plaza_id  = EXCLUDED.from_plaza_id,
            to_plaza_id    = EXCLUDED.to_plaza_id,
            category_index = EXCLUDED.category_index,
            fare           = EXCLUDED.fare,
            updated_at     = EXCLUDED.updated_at
    """, rows)
    return len(rows)


def pull_tags(master_cur, local_cur) -> int:
    """Full refresh — small table, catches all status/assignment changes from master."""
    master_cur.execute("""
        SELECT id, tag_serial, tid, epc, vehicle_id, issued_at,
               expiry_date, status, last_scanned_at, updated_at
        FROM tags
    """)
    rows = master_cur.fetchall()
    if not rows:
        return 0
    try:
        local_cur.execute("SAVEPOINT pull_tags")
        psycopg2.extras.execute_values(local_cur, """
            INSERT INTO tags (id, tag_serial, tid, epc, vehicle_id, issued_at,
                   expiry_date, status, last_scanned_at, updated_at)
            VALUES %s
            ON CONFLICT (id) DO UPDATE SET
                status          = EXCLUDED.status,
                tid             = EXCLUDED.tid,
                vehicle_id      = EXCLUDED.vehicle_id,
                expiry_date     = EXCLUDED.expiry_date,
                last_scanned_at = EXCLUDED.last_scanned_at,
                updated_at      = EXCLUDED.updated_at
            WHERE tags.updated_at < EXCLUDED.updated_at
        """, rows)
        local_cur.execute("RELEASE SAVEPOINT pull_tags")
    except Exception:
        local_cur.execute("ROLLBACK TO SAVEPOINT pull_tags")
        psycopg2.extras.execute_values(local_cur, """
            INSERT INTO tags (id, tag_serial, tid, epc, vehicle_id, issued_at,
                   expiry_date, status, last_scanned_at, updated_at)
            VALUES %s
            ON CONFLICT DO NOTHING
        """, rows)
        log.warning("[pull] tags: conflict on unique constraint — skipped conflicting rows")
    return len(rows)


# ── Timestamp-tracked tables ──────────────────────────────────────────────────

def pull_users(master_cur, local_cur, since: datetime) -> int:
    master_cur.execute("""
        SELECT id, password, last_login, is_superuser, uuid, full_name,
               cnic, phone, user_role, status, is_staff, created_at,
               updated_at, created_by_id, last_login_at
        FROM users WHERE updated_at > %s OR created_at > %s
    """, (since, since))
    rows = master_cur.fetchall()
    if not rows:
        return 0
    psycopg2.extras.execute_values(local_cur, """
        INSERT INTO users (id, password, last_login, is_superuser, uuid,
               full_name, cnic, phone, user_role, status, is_staff,
               created_at, updated_at, created_by_id, last_login_at)
        VALUES %s
        ON CONFLICT (id) DO UPDATE SET
            password    = EXCLUDED.password,
            full_name   = EXCLUDED.full_name,
            cnic        = EXCLUDED.cnic,
            phone       = EXCLUDED.phone,
            status      = EXCLUDED.status,
            user_role   = EXCLUDED.user_role,
            updated_at  = EXCLUDED.updated_at
        WHERE users.updated_at < EXCLUDED.updated_at
    """, rows)
    return len(rows)


def pull_vehicles(master_cur, local_cur, since: datetime) -> int:
    master_cur.execute("""
        SELECT id, owner_id, plate_number, vehicle_type, status,
               registered_at, updated_at
        FROM vehicles WHERE updated_at > %s OR registered_at > %s
    """, (since, since))
    rows = master_cur.fetchall()
    if not rows:
        return 0
    try:
        local_cur.execute("SAVEPOINT pull_vehicles")
        psycopg2.extras.execute_values(local_cur, """
            INSERT INTO vehicles (id, owner_id, plate_number, vehicle_type,
                   status, registered_at, updated_at)
            VALUES %s
            ON CONFLICT (id) DO UPDATE SET
                status       = EXCLUDED.status,
                plate_number = EXCLUDED.plate_number,
                vehicle_type = EXCLUDED.vehicle_type,
                updated_at   = EXCLUDED.updated_at
            WHERE vehicles.updated_at < EXCLUDED.updated_at
        """, rows)
        local_cur.execute("RELEASE SAVEPOINT pull_vehicles")
    except Exception:
        local_cur.execute("ROLLBACK TO SAVEPOINT pull_vehicles")
        psycopg2.extras.execute_values(local_cur, """
            INSERT INTO vehicles (id, owner_id, plate_number, vehicle_type,
                   status, registered_at, updated_at)
            VALUES %s
            ON CONFLICT DO NOTHING
        """, rows)
        log.warning("[pull] vehicles: conflict on unique constraint — skipped conflicting rows")
    return len(rows)


def pull_accounts(master_cur, local_cur, since: datetime) -> int:
    """
    Timestamp guard on DO UPDATE: only update local balance if master's
    balance_updated_at is newer. This prevents a master pull from overwriting
    a balance that was already deducted locally during an offline exit.
    """
    master_cur.execute("""
        SELECT id, vehicle_id, user_id, balance, created_at, balance_updated_at
        FROM accounts
        WHERE balance_updated_at > %s OR created_at > %s
    """, (since, since))
    rows = master_cur.fetchall()
    if not rows:
        return 0
    # Pre-filter: skip accounts whose vehicle_id doesn't exist locally
    vehicle_ids = [str(r[1]) for r in rows]
    local_cur.execute("SELECT id FROM vehicles WHERE id = ANY(%s::bigint[])", (vehicle_ids,))
    existing = {str(r[0]) for r in local_cur.fetchall()}
    rows = [r for r in rows if str(r[1]) in existing]
    if not rows:
        log.warning("[pull] accounts: all skipped — vehicle_ids not present locally")
        return 0
    skipped = len(vehicle_ids) - len(rows)
    if skipped:
        log.warning("[pull] accounts: %d skipped — vehicle_id not present locally", skipped)
    psycopg2.extras.execute_values(local_cur, """
        INSERT INTO accounts (id, vehicle_id, user_id, balance,
               created_at, balance_updated_at)
        VALUES %s
        ON CONFLICT (id) DO UPDATE SET
            balance            = EXCLUDED.balance,
            balance_updated_at = EXCLUDED.balance_updated_at
        WHERE accounts.balance_updated_at < EXCLUDED.balance_updated_at
    """, rows)
    return len(rows)


def pull_reference(master_cur, local_cur) -> dict:
    """Master-owned reference data. Required by BOTH booth modes.

    Without this an entry booth has no tags/vehicles/accounts to validate against
    and would reject every vehicle, and an exit booth has no rates to price with.
    """
    summary = {}
    # Full-refresh tables (no usable timestamp column)
    summary['plazas']     = pull_plazas(master_cur, local_cur)
    summary['toll_lanes'] = pull_toll_lanes(master_cur, local_cur)
    summary['toll_rates'] = pull_toll_rates(master_cur, local_cur)
    summary['tags']       = pull_tags(master_cur, local_cur)
    # Categories before fares: fare_matrix FKs both plazas and categories.
    summary['vehicle_categories'] = pull_vehicle_categories(master_cur, local_cur)
    summary['fare_matrix']        = pull_fare_matrix(master_cur, local_cur)
    summary['tag_assignments']    = pull_tag_assignments(master_cur, local_cur)

    # Timestamp-tracked tables
    for table, fn in [
        ('users',    pull_users),
        ('vehicles', pull_vehicles),
        ('accounts', pull_accounts),
    ]:
        since = _get_last_pull(local_cur, table)
        count = fn(master_cur, local_cur, since)
        if count:
            _set_last_pull(local_cur, table, _now())
        summary[table] = count

    # Every row above arrived with master's id, bypassing each table's sequence.
    # Without this the booth's next locally-created row collides on the pkey.
    _resync_all(local_cur)
    return summary


def pull_trips(master_cur, local_cur, include_open: bool) -> dict:
    """Trip lifecycle. `include_open` should be True only for EXIT booths.

    An entry booth has no use for other plazas' open trips — it never charges
    against them — but it DOES need the closed-trip pass, or a completed trip
    stays 'active' in its local DB and blocks that vehicle's next entry.
    """
    return sync_trip_lifecycle(master_cur, local_cur, include_open=include_open)


def run_pull(mode: str = 'exit') -> dict:
    """Pull from master into the local DB, according to booth mode.

    mode='entry' — reference data + closed trips.
    mode='exit'  — reference data + closed trips + OPEN trips.

    Defaults to 'exit' (the superset) so an unset/typo\'d mode degrades to
    pulling more rather than silently starving an exit lane of open trips.
    """
    summary = {'mode': mode}
    try:
        master_conn = get_master_conn()
        local_conn  = get_local_conn()
    except Exception as exc:
        log.warning("[pull] Cannot connect: %s", exc)
        return {'error': str(exc), 'mode': mode}

    try:
        with master_conn, local_conn:
            with master_conn.cursor() as mc, local_conn.cursor() as lc:
                summary.update(pull_reference(mc, lc))
                trips = pull_trips(mc, lc, include_open=(mode != 'entry'))
                summary['open_trips']   = trips['active']
                summary['closed_trips'] = trips['closed']

        log.info("[pull] done — %s", summary)
    except Exception as exc:
        log.error("[pull] error: %s", exc)
        summary['error'] = str(exc)
    finally:
        master_conn.close()
        local_conn.close()

    return summary

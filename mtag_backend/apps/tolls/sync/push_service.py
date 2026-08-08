"""
PUSH service: booth → master. One half of the sync service; see pull_service.py
for the other. Nothing in here is called from the RFID/gate path — the gate only
ever writes to the local database, and this process moves those writes to master.

Tables pushed:
  - users        — new/updated users (operators, vehicle owners)
  - vehicles     — new registrations + status changes
  - tags         — tag assignments (vehicle_id), tid, status changes
  - accounts     — balance changes
  - toll_trips   — uses updated_at so BOTH new entries AND exit updates reach master
  - transactions — new records only (immutable, use processed_at)

Design for toll_trips:
  Entry gate creates a trip locally (updated_at advances) → pushed as INSERT.
  Exit gate updates that trip locally (updated_at advances) → pushed as UPDATE.
  Two guards protect master: the updated_at timestamp guard stops a stale row
  overwriting a fresher one, and the exit_time pre-filter stops a second lane
  overwriting an exit master has already recorded (see push_toll_trips).

WATERMARK RULE — the reason PushFailed exists:
  run_push() advances a table's sync_log watermark ONLY when that table's push
  fully succeeded. The previous version returned len(rows) even after rolling
  back, so the watermark advanced past rows that were never written and
  `WHERE updated_at > since` never selected them again — trips, transactions and
  balances were silently and permanently lost from master. Any partial or failed
  push now raises PushFailed, leaves the watermark alone, and is retried next
  cycle. Retrying noisily is always preferable to losing financial records.
"""
import logging
from datetime import datetime, timezone

import psycopg2.extras

from apps.tolls.sync.connections import get_local_conn, get_master_conn

log = logging.getLogger('apps.tolls.sync.push')


class PushFailed(Exception):
    """A push pass did not fully succeed — its watermark must NOT advance."""


def _now():
    return datetime.now(timezone.utc)


def _get_last_push(local_cur, table: str):
    local_cur.execute(
        "SELECT last_push_at FROM sync_log WHERE table_name = %s", (table,)
    )
    row = local_cur.fetchone()
    if row and row[0]:
        return row[0]
    return datetime(2000, 1, 1, tzinfo=timezone.utc)


def _set_last_push(local_cur, table: str, ts: datetime):
    local_cur.execute("""
        INSERT INTO sync_log (table_name, last_push_at)
        VALUES (%s, %s)
        ON CONFLICT (table_name) DO UPDATE SET last_push_at = EXCLUDED.last_push_at
    """, (table, ts))


def _guarded(master_cur, name, sql, rows):
    """Run one batched upsert inside a SAVEPOINT.

    Every pass is wrapped so a failure in one table cannot poison the shared
    master transaction and take the other tables down with it. Failure is
    converted to PushFailed so run_push() holds the watermark.
    """
    try:
        master_cur.execute(f"SAVEPOINT {name}")
        psycopg2.extras.execute_values(master_cur, sql, rows)
        master_cur.execute(f"RELEASE SAVEPOINT {name}")
    except Exception as exc:
        master_cur.execute(f"ROLLBACK TO SAVEPOINT {name}")
        raise PushFailed(f"{name}: {exc.__class__.__name__}: {exc}") from exc



def _resync_sequence(cur, table: str, column: str = 'id') -> None:
    """Realign a serial sequence after inserting rows with explicit ids.

    The sync upserts rows using the ids the other side assigned, which bypasses
    the sequence completely — it stays where it was while the data moves ahead.
    The next locally-created row then reuses an id that is already taken and the
    INSERT dies with "duplicate key value violates unique constraint <t>_pkey".
    Seen in the wild: a booth that had pulled users could not register a new one.

    Only integer-PK tables need this. Everything else the sync touches (vehicles,
    tags, accounts, plazas, trips, fares) uses UUIDs, which have no sequence.
    """
    cur.execute(
        "SELECT setval(pg_get_serial_sequence(%s, %s), "
        "       GREATEST(COALESCE((SELECT MAX(" + column + ") FROM " + table + "), 1), 1))",
        (f"public.{table}", column),
    )


# ── users ─────────────────────────────────────────────────────────────────────

def push_users(local_cur, master_cur, since: datetime) -> int:
    local_cur.execute("""
        SELECT id, password, last_login, is_superuser, uuid, full_name,
               cnic, phone, user_role, status, is_staff, created_at,
               updated_at, created_by_id, last_login_at
        FROM users WHERE updated_at > %s OR created_at > %s
    """, (since, since))
    rows = local_cur.fetchall()
    if not rows:
        return 0
    _guarded(master_cur, 'push_users', """
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
    # Same hazard in reverse: master receives booth-assigned ids.
    _resync_sequence(master_cur, 'users')
    return len(rows)


# ── vehicles ──────────────────────────────────────────────────────────────────

def push_vehicles(local_cur, master_cur, since: datetime) -> int:
    local_cur.execute("""
        SELECT id, owner_id, plate_number, vehicle_type, status,
               registered_at, updated_at
        FROM vehicles WHERE updated_at > %s OR registered_at > %s
    """, (since, since))
    rows = local_cur.fetchall()
    if not rows:
        return 0
    _guarded(master_cur, 'push_vehicles', """
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
    return len(rows)


# ── tags ──────────────────────────────────────────────────────────────────────

def push_tags(local_cur, master_cur, since: datetime) -> int:
    """Push tag assignments, status changes, and tid.

    tid is load-bearing: EntryService/ExitService look tags up by tid only, so a
    tag whose tid never reaches master (and from there the other booths) can
    never open a barrier anywhere else on the network.
    """
    local_cur.execute("""
        SELECT id, tag_serial, tid, epc, vehicle_id, issued_at,
               expiry_date, status, last_scanned_at, updated_at
        FROM tags WHERE updated_at > %s
    """, (since,))
    rows = local_cur.fetchall()
    if not rows:
        return 0
    _guarded(master_cur, 'push_tags', """
        INSERT INTO tags (id, tag_serial, tid, epc, vehicle_id, issued_at,
               expiry_date, status, last_scanned_at, updated_at)
        VALUES %s
        ON CONFLICT (id) DO UPDATE SET
            vehicle_id      = EXCLUDED.vehicle_id,
            tid             = EXCLUDED.tid,
            status          = EXCLUDED.status,
            expiry_date     = EXCLUDED.expiry_date,
            last_scanned_at = EXCLUDED.last_scanned_at,
            updated_at      = EXCLUDED.updated_at
        WHERE tags.updated_at < EXCLUDED.updated_at
    """, rows)
    return len(rows)


# ── tag assignments ───────────────────────────────────────────────────────────

def push_tag_assignments(local_cur, master_cur, since: datetime) -> int:
    """Push tag installation history to master.

    Reissues happen AT booths, so without this the audit trail of which vehicle
    a tag was fitted to only ever exists on the booth that did the swap.
    """
    local_cur.execute(
        "SELECT id, tag_id, tag_serial, vehicle_id, plate_number, assigned_at, assigned_by_id, removed_at, removed_reason, notes, created_at, updated_at FROM tag_assignments WHERE updated_at > %s", (since,)
    )
    rows = local_cur.fetchall()
    if not rows:
        return 0
    _guarded(master_cur, 'push_tag_assignments', """
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


# ── accounts ──────────────────────────────────────────────────────────────────

def push_accounts(local_cur, master_cur, since: datetime) -> int:
    """Push balance changes to master.

    KNOWN LIMITATION of asynchronous balance replication: this is last-writer-
    wins on balance_updated_at, so two booths charging the same account inside
    one sync interval will lose one deduction (master keeps the later absolute
    balance, not the sum of both charges). Transactions are the durable record —
    reconcile balances from `transactions` rather than trusting this column if
    the two ever disagree.
    """
    local_cur.execute("""
        SELECT id, vehicle_id, user_id, balance, created_at, balance_updated_at
        FROM accounts WHERE balance_updated_at > %s
    """, (since,))
    rows = local_cur.fetchall()
    if not rows:
        return 0
    _guarded(master_cur, 'push_accounts', """
        INSERT INTO accounts (id, vehicle_id, user_id, balance,
               created_at, balance_updated_at)
        VALUES %s
        ON CONFLICT (id) DO UPDATE SET
            balance            = EXCLUDED.balance,
            balance_updated_at = EXCLUDED.balance_updated_at
        WHERE accounts.balance_updated_at < EXCLUDED.balance_updated_at
    """, rows)
    return len(rows)


# ── toll_trips ────────────────────────────────────────────────────────────────

def push_toll_trips(local_cur, master_cur, since: datetime) -> int:
    """Push new entry trips and completed exit trips.

    Double-charge protection: master is asked which of these trips it has ALREADY
    closed (exit_time IS NOT NULL). Those are excluded and logged at ERROR — a
    booth trying to push an exit for a trip master already closed means two lanes
    both charged the same trip, which needs a human. Master keeps the first exit.
    """
    local_cur.execute("""
        SELECT id, vehicle_id, tag_id, account_id, entry_plaza_id,
               entry_lane_id, entry_time, exit_plaza_id, exit_lane_id,
               exit_time, charge_amount, balance_before, balance_after,
               status, created_at, updated_at
        FROM toll_trips WHERE updated_at > %s
    """, (since,))
    rows = local_cur.fetchall()
    if not rows:
        return 0

    trip_ids = [str(r[0]) for r in rows]
    master_cur.execute(
        "SELECT id FROM toll_trips WHERE id = ANY(%s::uuid[]) AND exit_time IS NOT NULL",
        (trip_ids,),
    )
    already_closed = {str(r[0]) for r in master_cur.fetchall()}
    if already_closed:
        # Only a conflict if THIS booth is also asserting an exit (index 9).
        conflicting = [r for r in rows if str(r[0]) in already_closed and r[9] is not None]
        for r in conflicting:
            log.error(
                "[push] toll_trips: REFUSING exit for trip %s — master already "
                "recorded an exit. Two lanes charged the same trip; master's "
                "original exit is kept. Investigate.", r[0]
            )
        rows = [r for r in rows if str(r[0]) not in already_closed]
        if not rows:
            return 0

    _guarded(master_cur, 'push_toll_trips', """
        INSERT INTO toll_trips (id, vehicle_id, tag_id, account_id,
               entry_plaza_id, entry_lane_id, entry_time,
               exit_plaza_id, exit_lane_id, exit_time,
               charge_amount, balance_before, balance_after,
               status, created_at, updated_at)
        VALUES %s
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
    """, rows)
    return len(rows)


# ── transactions ──────────────────────────────────────────────────────────────

def push_transactions(local_cur, master_cur, since: datetime) -> int:
    """Transactions are immutable — push new ones only, keyed on processed_at."""
    local_cur.execute("""
        SELECT id, account_id, toll_trip_id, toll_lane_id, tag_serial, amount,
               transaction_type, balance_before, balance_after, status,
               source, idempotency_key, reference_id, processed_at
        FROM transactions WHERE processed_at > %s
    """, (since,))
    rows = local_cur.fetchall()
    if not rows:
        return 0

    # An account missing on master means push_accounts has not landed yet. That
    # is a transient ordering issue, not a reason to drop money records — raise
    # so the watermark holds and the same rows are retried next cycle.
    account_ids = [str(r[1]) for r in rows]
    master_cur.execute("SELECT id FROM accounts WHERE id = ANY(%s::uuid[])", (account_ids,))
    existing = {str(r[0]) for r in master_cur.fetchall()}
    missing = [a for a in account_ids if a not in existing]
    if missing:
        raise PushFailed(
            f"push_transactions: {len(missing)} transaction(s) reference accounts "
            f"not yet on master (e.g. {missing[0]}) — retrying next cycle"
        )

    _guarded(master_cur, 'push_transactions', """
        INSERT INTO transactions (id, account_id, toll_trip_id,
               toll_lane_id, tag_serial, amount,
               transaction_type, balance_before, balance_after, status,
               source, idempotency_key, reference_id, processed_at)
        VALUES %s
        ON CONFLICT (id) DO NOTHING
    """, rows)
    return len(rows)


# ── entry point ───────────────────────────────────────────────────────────────

# Order matters: master's FKs require the referenced rows to exist first.
PUSH_PASSES = [
    ('users',        push_users),
    ('vehicles',     push_vehicles),
    ('tags',         push_tags),
    ('accounts',     push_accounts),
    ('tag_assignments', push_tag_assignments),
    ('toll_trips',   push_toll_trips),
    ('transactions', push_transactions),
]


def run_push() -> dict:
    """Push locally-created/updated records to master. Returns a summary dict.

    Both booth modes run this: an entry booth to publish the trips it starts, an
    exit booth to publish the exits and transactions it completes.
    """
    summary = {}
    try:
        local_conn  = get_local_conn()
        master_conn = get_master_conn()
    except Exception as exc:
        log.warning("[push] Cannot connect to master: %s", exc)
        return {'error': str(exc)}

    try:
        with local_conn, master_conn:
            with local_conn.cursor() as lc, master_conn.cursor() as mc:
                for table, fn in PUSH_PASSES:
                    since = _get_last_push(lc, table)
                    try:
                        count = fn(lc, mc, since)
                    except PushFailed as exc:
                        # Watermark deliberately NOT advanced — retried next cycle.
                        log.error("[push] %s FAILED, watermark held: %s", table, exc)
                        summary[table] = f'failed: {exc}'
                        continue
                    if count:
                        _set_last_push(lc, table, _now())
                    summary[table] = count

        log.info("[push] done — %s", summary)
    except Exception as exc:
        log.error("[push] error: %s", exc)
        summary['error'] = str(exc)
    finally:
        local_conn.close()
        master_conn.close()

    return summary

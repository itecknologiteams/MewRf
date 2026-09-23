"""What this booth has actually been doing, kept where the console can read it.

The gate prints everything it decides, and until now that was the only record:
`pm2 logs mtag-gate`. That is fine for watching a lane over someone's shoulder
and useless for the two questions an engineer standing at a booth actually has —
"is the reader seeing this tag at all, and at what signal?" and "did the barrier
get the command?" — because the log only reports RSSI on a *stage change*, drops
everything on rotation, and cannot be queried.

So the gate also writes here: a small, capped SQLite file next to manage.py that
the web process reads. Two processes, one file, which is why it is SQLite in WAL
mode rather than a Python structure — `mtag-gate` and `mtag-web` are separate PM2
apps and share no memory.

Three rules this module is built around, in order of importance:

  1. **It must never be able to stall the gate.** One thread handles every
     vehicle in the lane; a write that blocks on a locked database blocks the
     barrier. So callers only ever put onto a bounded in-memory queue and return
     — a full queue DROPS the record rather than waiting, and every public
     recording method swallows its own exceptions. Losing a diagnostic row is a
     cost worth paying; holding up a car is not.

  2. **It must not grow without bound.** A booth runs for months between
     restarts and its disk is small. Each table is a ring buffer trimmed to a
     row ceiling, so the file reaches a steady size and stays there.

  3. **Reads must not disturb writes.** The web process only ever SELECTs, and
     WAL means its reads never block the gate's inserts.

Nothing financial lives here. Trips, charges and balances are master's, and this
file can be deleted at any time — the gate recreates it and nothing is lost but
the recent history the console draws.
"""

import logging
import os
import queue
import sqlite3
import threading
import time

logger = logging.getLogger(__name__)

DB_FILENAME = 'booth_activity.db'

# Row ceilings. Reads dominate by an order of magnitude — the reader reports
# every tag in the field on every inventory pass, whether or not anything comes
# of it — so it gets the larger share. At ~5 reads/second on a busy lane, 20k
# rows is a bit over an hour of continuous traffic, which is the window someone
# tuning a lane actually scrolls back through.
MAX_TAG_READS = 20000
MAX_GATE_EVENTS = 5000
MAX_BARRIER_COMMANDS = 5000

# Bounded so a wedged writer cannot consume the gate's memory. Past this, records
# are dropped and counted (see `stats()`), which is the honest failure: the
# console can then say "diagnostics dropped N rows" instead of quietly lying by
# omission.
QUEUE_MAXSIZE = 4000

FLUSH_INTERVAL = 0.5     # seconds between batch writes
TRIM_INTERVAL = 120.0    # seconds between ring-buffer trims

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tag_reads (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        REAL    NOT NULL,
    epc       TEXT    NOT NULL DEFAULT '',
    tid       TEXT    NOT NULL DEFAULT '',
    rssi      REAL,
    median    REAL,
    samples   INTEGER NOT NULL DEFAULT 0,
    stage     TEXT    NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_tag_reads_ts ON tag_reads(ts);

CREATE TABLE IF NOT EXISTS gate_events (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        REAL    NOT NULL,
    kind      TEXT    NOT NULL,
    tid       TEXT    NOT NULL DEFAULT '',
    epc       TEXT    NOT NULL DEFAULT '',
    plate     TEXT    NOT NULL DEFAULT '',
    result    TEXT    NOT NULL DEFAULT '',
    reason    TEXT    NOT NULL DEFAULT '',
    charge    TEXT    NOT NULL DEFAULT '',
    balance   TEXT    NOT NULL DEFAULT '',
    offline   INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_gate_events_ts ON gate_events(ts);

CREATE TABLE IF NOT EXISTS barrier_commands (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        REAL    NOT NULL,
    action    TEXT    NOT NULL,
    source    TEXT    NOT NULL DEFAULT '',
    backend   TEXT    NOT NULL DEFAULT '',
    ok        INTEGER NOT NULL DEFAULT 1,
    detail    TEXT    NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_barrier_commands_ts ON barrier_commands(ts);
"""

_INSERTS = {
    'tag_reads': (
        "INSERT INTO tag_reads (ts, epc, tid, rssi, median, samples, stage) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)"
    ),
    'gate_events': (
        "INSERT INTO gate_events "
        "(ts, kind, tid, epc, plate, result, reason, charge, balance, offline) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    ),
    'barrier_commands': (
        "INSERT INTO barrier_commands (ts, action, source, backend, ok, detail) "
        "VALUES (?, ?, ?, ?, ?, ?)"
    ),
}

_CEILINGS = {
    'tag_reads': MAX_TAG_READS,
    'gate_events': MAX_GATE_EVENTS,
    'barrier_commands': MAX_BARRIER_COMMANDS,
}


def get_db_path() -> str:
    """Default path: {manage.py dir}/booth_activity.db — beside offline_cache.db."""
    manage_dir = os.path.dirname(
        os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', '..', 'manage.py')
        )
    )
    return os.path.join(manage_dir, DB_FILENAME)


def _connect(db_path: str, *, create: bool) -> sqlite3.Connection:
    """Open a connection with the pragmas both ends rely on.

    `create=False` opens read-only over a URI so the web process can never
    create a half-built database on a host that has no gate — the console then
    reports "no activity recorded" rather than inventing an empty one.
    """
    if create:
        conn = sqlite3.connect(db_path, timeout=5.0, check_same_thread=False)
    else:
        uri = 'file:' + db_path.replace('?', '%3f').replace('#', '%23') + '?mode=ro'
        try:
            conn = sqlite3.connect(uri, uri=True, timeout=5.0, check_same_thread=False)
        except sqlite3.OperationalError:
            # A path the URI form cannot express (a Windows drive letter, an
            # exotic character). Callers only ever reach here for a file they
            # have already confirmed exists, and only ever SELECT from it, so
            # opening it the ordinary way creates nothing and changes nothing.
            conn = sqlite3.connect(db_path, timeout=5.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    if create:
        # WAL is the whole reason two processes can share this file: the web
        # process's SELECTs never block the gate's INSERTs and vice versa.
        conn.execute("PRAGMA journal_mode=WAL;")
        # Deliberately NOT synchronous=FULL, unlike offline_cache. That file
        # holds exits that owe money and must survive a power cut; this one
        # holds diagnostics. Paying an fsync per batch to protect the last
        # half-second of RSSI readings would be spending the lane's disk
        # latency on nothing.
        conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


class ActivityRecorder:
    """Queues activity from the gate and writes it in batches on its own thread.

    One per process. The gate calls the `record_*` methods from the SDK's receive
    thread and from the portal-poll thread; both are hot paths, so each method
    does nothing but build a tuple and `put_nowait` it.
    """

    def __init__(self, db_path=None):
        self.db_path = db_path or get_db_path()
        self._q: queue.Queue = queue.Queue(maxsize=QUEUE_MAXSIZE)
        self._dropped = 0
        self._written = 0
        self._lock = threading.Lock()
        self._running = True
        self._ready = threading.Event()
        self._start_error = ''
        self._thread = threading.Thread(
            target=self._run, name='booth-activity', daemon=True)
        self._thread.start()

    # ── Recording (hot path — must not block, must not raise) ────────────────

    def _put(self, table: str, row: tuple):
        try:
            self._q.put_nowait((table, row))
        except queue.Full:
            # Counted rather than logged: a full queue means the writer is
            # already struggling, and a log line per drop would make that worse.
            with self._lock:
                self._dropped += 1
        except Exception:
            pass

    def record_read(self, *, epc, tid, rssi, median, samples, stage):
        """One tag read, exactly as the reader reported it plus the gate's verdict."""
        try:
            self._put('tag_reads', (
                time.time(), epc or '', tid or '',
                float(rssi) if rssi is not None else None,
                float(median) if median is not None else None,
                int(samples or 0), stage or '',
            ))
        except Exception:
            pass

    def record_gate_event(self, *, kind, tid='', epc='', plate='', result='',
                          reason='', charge='', balance='', offline=False):
        """A decision: a balance preview, a charged trip, or a refusal."""
        try:
            self._put('gate_events', (
                time.time(), kind, tid or '', epc or '', plate or '',
                result or '', reason or '', str(charge or ''), str(balance or ''),
                1 if offline else 0,
            ))
        except Exception:
            pass

    def record_barrier(self, *, action, source='', backend='', ok=True, detail=''):
        """A barrier command as the gate issued it — not as the boom answered.

        Nothing on a booth reports back that the barrier physically moved, so
        `ok` means "the command was dispatched" and no more. See
        BarrierBackend.open's docstring for the same distinction.
        """
        try:
            self._put('barrier_commands', (
                time.time(), action, source or '', backend or '',
                1 if ok else 0, detail or '',
            ))
        except Exception:
            pass

    # ── Writer thread ────────────────────────────────────────────────────────

    def _run(self):
        try:
            conn = _connect(self.db_path, create=True)
            conn.executescript(_SCHEMA_SQL)
            conn.commit()
        except Exception as exc:
            # A booth with a read-only or full disk must still run its lane. Say
            # so once, then stop — the console reports the recorder as down.
            self._start_error = str(exc)
            self._ready.set()
            logger.warning("[activity] Recorder disabled — cannot open %s: %s",
                           self.db_path, exc)
            return

        self._ready.set()
        last_trim = time.monotonic()
        try:
            while True:
                batch = self._drain()
                if batch is None:
                    return
                if batch:
                    self._write(conn, batch)
                now = time.monotonic()
                if now - last_trim >= TRIM_INTERVAL:
                    last_trim = now
                    self._trim(conn)
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _drain(self):
        """Collect one batch, blocking until there is something to write.

        Returns None when the sentinel arrives, which is the only way out.
        """
        batch = []
        try:
            first = self._q.get(timeout=FLUSH_INTERVAL)
        except queue.Empty:
            return batch
        if first is None:
            return None
        batch.append(first)
        # Take whatever else is already waiting, so a burst costs one
        # transaction rather than one per row.
        while len(batch) < 500:
            try:
                item = self._q.get_nowait()
            except queue.Empty:
                break
            if item is None:
                # Shutdown arrived mid-burst. Write what we have first, then
                # stop on the next pass — a dropped sentinel would hang the
                # close(), so put it back.
                self._q.put_nowait(None)
                break
            batch.append(item)
        return batch

    def _write(self, conn, batch):
        grouped: dict = {}
        for table, row in batch:
            grouped.setdefault(table, []).append(row)
        try:
            with conn:
                for table, rows in grouped.items():
                    conn.executemany(_INSERTS[table], rows)
            with self._lock:
                self._written += len(batch)
        except Exception as exc:
            logger.warning("[activity] Batch write failed (%d rows): %s",
                           len(batch), exc)

    def _trim(self, conn):
        """Hold each table at its ceiling. Oldest rows go first."""
        try:
            with conn:
                for table, ceiling in _CEILINGS.items():
                    conn.execute(
                        f"DELETE FROM {table} WHERE id <= ("
                        f"  SELECT MAX(id) - ? FROM {table}"
                        f")",
                        (ceiling,),
                    )
        except Exception as exc:
            logger.warning("[activity] Trim failed: %s", exc)

    # ── Status / shutdown ────────────────────────────────────────────────────

    def stats(self) -> dict:
        with self._lock:
            return {
                'db_path': self.db_path,
                'running': self._thread.is_alive(),
                'error': self._start_error,
                'queued': self._q.qsize(),
                'written': self._written,
                'dropped': self._dropped,
            }

    def close(self, timeout=3.0):
        self._running = False
        try:
            self._q.put_nowait(None)
        except queue.Full:
            pass
        self._thread.join(timeout=timeout)


# ── Process-wide recorder ────────────────────────────────────────────────────

_recorder = None
_recorder_lock = threading.Lock()


def get_recorder() -> ActivityRecorder:
    """The recorder for this process, started on first use."""
    global _recorder
    with _recorder_lock:
        if _recorder is None:
            _recorder = ActivityRecorder()
        return _recorder


class NullRecorder:
    """Accepts and discards everything. Used where recording is switched off."""

    def record_read(self, **kwargs):
        pass

    def record_gate_event(self, **kwargs):
        pass

    def record_barrier(self, **kwargs):
        pass

    def stats(self):
        return {'running': False, 'error': 'disabled', 'queued': 0,
                'written': 0, 'dropped': 0, 'db_path': ''}

    def close(self, timeout=0):
        pass


# ── Reading (the web process's side) ─────────────────────────────────────────

def _query(sql: str, params=(), db_path=None) -> list:
    """Run one SELECT against the activity file, or return [] if there is none.

    Every failure answers the same way — an absent file, a booth where the gate
    has never run, a locked database — because to the console they mean the same
    thing: no activity to show. The console distinguishes them via `recorder`
    in the overview payload.
    """
    path = db_path or get_db_path()
    if not os.path.exists(path):
        return []
    conn = None
    try:
        conn = _connect(path, create=False)
        return [dict(row) for row in conn.execute(sql, params)]
    except Exception as exc:
        logger.debug("[activity] Read failed: %s", exc)
        return []
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _page(table: str, columns: str, limit: int, since_id=None, db_path=None) -> list:
    """The newest `limit` rows, or everything after `since_id`, oldest first.

    `since_id` is what makes the console's polling cheap: it asks for what it has
    not seen rather than re-fetching the window every two seconds.
    """
    limit = max(1, min(int(limit or 200), 2000))
    if since_id:
        rows = _query(
            f"SELECT {columns} FROM {table} WHERE id > ? ORDER BY id ASC LIMIT ?",
            (int(since_id), limit), db_path,
        )
        return rows
    rows = _query(
        f"SELECT {columns} FROM {table} ORDER BY id DESC LIMIT ?",
        (limit,), db_path,
    )
    rows.reverse()
    return rows


def read_tag_reads(limit=300, since_id=None, db_path=None) -> list:
    return _page(
        'tag_reads', 'id, ts, epc, tid, rssi, median, samples, stage',
        limit, since_id, db_path,
    )


def read_gate_events(limit=100, since_id=None, db_path=None) -> list:
    return _page(
        'gate_events',
        'id, ts, kind, tid, epc, plate, result, reason, charge, balance, offline',
        limit, since_id, db_path,
    )


def read_barrier_commands(limit=100, since_id=None, db_path=None) -> list:
    return _page(
        'barrier_commands', 'id, ts, action, source, backend, ok, detail',
        limit, since_id, db_path,
    )


def read_summary(window_seconds=3600, db_path=None) -> dict:
    """Counts over the last window, for the console's stat tiles."""
    since = time.time() - window_seconds
    reads = _query(
        "SELECT COUNT(*) AS n, COUNT(DISTINCT tid) AS tags, "
        "       MIN(rssi) AS min_rssi, MAX(rssi) AS max_rssi "
        "FROM tag_reads WHERE ts >= ?", (since,), db_path,
    )
    stages = _query(
        "SELECT stage, COUNT(*) AS n FROM tag_reads WHERE ts >= ? GROUP BY stage",
        (since,), db_path,
    )
    events = _query(
        "SELECT result, COUNT(*) AS n FROM gate_events WHERE ts >= ? GROUP BY result",
        (since,), db_path,
    )
    opens = _query(
        "SELECT COUNT(*) AS n FROM barrier_commands "
        "WHERE ts >= ? AND action IN ('open', 'hold')", (since,), db_path,
    )
    head = reads[0] if reads else {}
    return {
        'window_seconds': window_seconds,
        'reads': head.get('n', 0) or 0,
        'distinct_tags': head.get('tags', 0) or 0,
        'min_rssi': head.get('min_rssi'),
        'max_rssi': head.get('max_rssi'),
        'stages': {r['stage']: r['n'] for r in stages},
        'results': {r['result']: r['n'] for r in events},
        'barrier_opens': (opens[0]['n'] if opens else 0) or 0,
    }

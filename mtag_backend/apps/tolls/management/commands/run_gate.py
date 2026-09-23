"""
Django management command that replaces rfid_final.py.

Reads rfid_config.ini, connects to the RFID reader over TCP, and on every
tag scan calls EntryService / ExitService directly (no HTTP round-trip).
Barrier control is via a serial port; display updates are fire-and-forget
HTTP GETs.

Usage:
    python manage.py run_gate
    python manage.py run_gate --config /path/to/rfid_config.ini
"""
import configparser
import logging
import os
import statistics
import threading
import time
from collections import deque
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import no_style
from django.db import InterfaceError, OperationalError, close_old_connections, connections

from apps.tolls import barrier as barrier_mod
from apps.tolls import booth_activity

# Ceiling on one continuous opening, however many vehicles keep extending it.
# A lane that has been open this long is not a convoy any more — it is a fault,
# and the boom coming down is what makes anyone notice.
MAX_CONTINUOUS_OPEN = 60.0

# How often one tag's balance may be re-queried and re-shown while it sits in
# range. Every read of every tag in the field comes through the preview path, so
# this is what keeps a queue of waiting cars off the database.
BALANCE_REFRESH_SECONDS = 5.0

# How often the idle greeting is repainted on a lane where nothing is happening.
# Only needed so a display power-cycled on its own comes back, so it is slow.
WELCOME_REFRESH_SECONDS = 60.0

log = logging.getLogger('apps.tolls.gate')

# Errors that mean "the socket is gone", as opposed to "the query was wrong".
# Only these are worth reconnecting for; a bad query would just fail again.
_DEAD_CONNECTION = (InterfaceError, OperationalError)


def db_call(fn, *args, **kwargs):
    """Run a database call on a connection that is actually alive.

    Django only recycles connections at request boundaries, and the gate has no
    requests: it is one long-lived process whose threads each hold a connection
    for the life of the booth. Worse, the thread that matters — the SDK's
    receive thread, where every tag scan is handled — touches the database only
    when a vehicle turns up. On a quiet lane that connection sits idle for as
    long as the quiet lasts, and whatever is between the gate and Postgres (a
    NAT table, a firewall, idle_session_timeout) eventually reaps it.

    Nothing notices, because nothing is looking. The next vehicle's query then
    raises OperationalError, the listener's blanket except swallows it, and the
    barrier stays down. And since the broken connection is never closed, every
    vehicle after it fails the same way — the lane is dead until the process is
    restarted, which is exactly the fault this fixes.

    So: recycle anything stale before the call, and if the call still dies on a
    connection that went away underneath it, throw that connection out and try
    once more on a fresh one. Genuine failures (a missing tag, an insufficient
    balance) are not retried — they never reach here as exceptions.
    """
    close_old_connections()
    try:
        return fn(*args, **kwargs)
    except _DEAD_CONNECTION as exc:
        log.warning("[db] connection lost (%s) — reconnecting and retrying", exc)
        # close_all() rather than close_old_connections(): the latter keeps a
        # connection whose error Django has not marked yet, which is precisely
        # the one that just failed.
        connections.close_all()
        return fn(*args, **kwargs)


def install_statement_timeout(timeout_ms: int, stdout=None):
    """Cap how long any query from THIS process may run.

    Booths are online-only, so every gate query goes to master — and master's
    own statement_timeout is 15 minutes. The tag-processing thread is the single
    thread that handles every vehicle, so one query wedged behind a lock or a
    bad plan takes the whole lane down with it for as long as that ceiling
    allows. Every query the gate issues is a point lookup; none has any business
    taking seconds, let alone minutes.

    Applied through connection_created rather than DATABASES['OPTIONS'] because
    master and booths share config.settings.lan. Putting it in settings would
    also cap `migrate`, `load_fares`, booth_deploy_worker and the portal's
    report queries, which legitimately run long. The signal fires per new
    connection, so it survives db_call's reconnects and covers every thread.

    Deliberately installed by the management commands and NOT by
    GateController.__init__: apps.py can start an AnprGateController inside the
    gunicorn web process, where this cap would silently apply to admin and
    reporting queries too.
    """
    from django.db.backends.signals import connection_created

    def _apply(sender, connection, **kwargs):
        if connection.alias != 'default':
            return  # master_pg sets its own, tighter, bound in services.py
        with connection.cursor() as cursor:
            cursor.execute(f"SET statement_timeout = {int(timeout_ms)}")

    # weak=False: the receiver is a local function and would otherwise be
    # garbage collected the moment this returns, silently doing nothing.
    connection_created.connect(_apply, weak=False)
    if stdout:
        stdout.write(f"[db] statement_timeout set to {timeout_ms}ms for this process")
    return _apply


def resolve_plaza_lane(plaza_id: str, plaza_row_id: str, lane_number: str, lane_id: str):
    """Resolve config's plaza_id/lane_number to the DB row ids the gate needs.

    `plaza_id` is the operator-assigned plaza number from Plaza.plaza_id (this
    replaced the old `plaza_code`). `plaza_row_id` is the raw Plaza.id escape
    hatch, used only when plaza_id is not set.

    Returns (plaza_row_id, lane_id) as ints — both PKs are integers, so they are
    returned as ints rather than strings. A stringified id ("3") would still
    satisfy the Django ORM but compares unequal to 3 in the SQLite offline cache
    and lands as text in the bigint columns the sync pushes.
    """
    from apps.tolls.models import Plaza, TollLane

    def _available():
        numbers = Plaza.objects.order_by('plaza_id').values_list('plaza_id', flat=True)
        return ', '.join(str(n) for n in numbers) or '(no plazas in DB — has the sync agent run?)'

    # `plaza_id` used to mean the Plaza UUID in this config file, and now means
    # the integer plaza number. Fail loudly rather than letting int() blow up
    # with an opaque error on a booth someone forgot to update.
    if plaza_id and '-' in plaza_id:
        raise CommandError(
            f"plaza_id = '{plaza_id}' looks like a UUID.\n"
            "In this config, plaza_id is now the operator-assigned plaza number "
            "(e.g. plaza_id = 3). Use the plaza_row_id key if you really do want "
            "to pin this booth to a raw Plaza.id."
        )

    # Resolve plaza
    if plaza_id:
        try:
            number = int(plaza_id)
        except ValueError:
            raise CommandError(
                f"plaza_id '{plaza_id}' in [gate] is not an integer.\n"
                f"Available plaza_ids: {_available()}"
            )
        try:
            plaza_row_id = Plaza.objects.get(plaza_id=number).id
        except Plaza.DoesNotExist:
            raise CommandError(
                f"Plaza with plaza_id {number} not found in DB.\n"
                f"Available plaza_ids: {_available()}"
            )
    elif not plaza_row_id:
        raise CommandError(
            f"Set plaza_id (e.g. plaza_id = 3) in config.\n"
            f"Available plaza_ids: {_available()}"
        )
    else:
        try:
            plaza_row_id = int(plaza_row_id)
        except ValueError:
            raise CommandError(
                f"plaza_row_id '{plaza_row_id}' in [gate] is not an integer.\n"
                "Plaza ids are integers now — prefer plaza_id (the operator-"
                f"assigned number). Available plaza_ids: {_available()}"
            )

    # Resolve lane. NB: TollLane.plaza_id is Django's FK column and holds the
    # Plaza row id — it is not Plaza.plaza_id, the number resolved above.
    if lane_number and not lane_id:
        try:
            lane = TollLane.objects.get(plaza_id=plaza_row_id, lane_number=int(lane_number))
            lane_id = lane.id
        except TollLane.DoesNotExist:
            raise CommandError(
                f"Lane {lane_number} not found for plaza {plaza_id or plaza_row_id}."
            )
    elif lane_id:
        try:
            lane_id = int(lane_id)
        except ValueError:
            raise CommandError(f"lane_id '{lane_id}' in [gate] is not an integer.")

    return plaza_row_id, lane_id or None


class Command(BaseCommand):
    help = "Run the RFID gate controller (replaces rfid_final.py)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--config',
            default='rfid_config.ini',
            help='Path to rfid_config.ini (default: rfid_config.ini in CWD)',
        )
        parser.add_argument(
            '--test-mode',
            action='store_true',
            default=False,
            help='Hardware test: open barrier on every scan without DB checks (for wiring/reader testing only)',
        )

    def handle(self, *args, **options):
        cfg_path = options['config']
        if not os.path.exists(cfg_path):
            raise CommandError(
                f"Config file not found: {cfg_path}\n"
                "Create rfid_config.ini next to manage.py (see sample below).\n\n"
                "[gate]\n"
                "mode = entry          # entry or exit\n"
                "plaza_id = 3          # operator-assigned plaza number\n"
                "lane_number = 1\n"
                "lane_id =             # optional uuid\n\n"
                "[scanner]\n"
                "reader_host = 192.168.78.8\n"
                "reader_port = 9090\n"
                "tag_cooldown = 5.0\n"
                "rssi_detect = 0        # dBm to notice a tag at all (0 = off)\n"
                "rssi_open_min = 0      # dBm band the barrier opens in (0 = off)\n"
                "rssi_open_max = 0      #   \"                                  \n"
                "rssi_window = 5        # reads to median over\n"
                "rssi_hysteresis = 3.0  # dB of slack before dropping a tag\n\n"
                "[barrier]\n"
                "port = /dev/ttyUSB0\n"
                "baudrate = 115200\n"
                "open_seconds = 2.0\n\n"
                "[display]\n"
                "display_ip = 192.168.78.12\n"
            )

        cfg = configparser.ConfigParser()
        cfg.read(cfg_path)

        gate_mode   = cfg.get('gate', 'mode',       fallback='entry').strip().lower()
        plaza_id    = cfg.get('gate', 'plaza_id',   fallback='').strip()
        plaza_row_id = cfg.get('gate', 'plaza_row_id',
                               fallback=cfg.get('gate', 'plaza_uuid', fallback='')).strip()
        lane_id     = cfg.get('gate', 'lane_id',    fallback='').strip() or None
        lane_number = cfg.get('gate', 'lane_number', fallback='').strip() or None
        reader_host = cfg.get('scanner', 'reader_host', fallback='192.168.78.8')
        reader_port = int(cfg.get('scanner', 'reader_port', fallback='9090'))
        tag_cooldown    = float(cfg.get('scanner', 'tag_cooldown',    fallback='5.0'))
        antenna_power   = int(cfg.get('scanner', 'antenna_power',   fallback='33'))
        scan_interval   = float(cfg.get('scanner', 'scan_interval',  fallback='1.0'))
        # Three thresholds, two stages. `rssi_detect` is the weakest read worth
        # reacting to at all — a tag at or above it gets its balance shown and
        # nothing more. The barrier only opens, and the trip is only charged,
        # while the tag sits inside [rssi_open_min, rssi_open_max].
        #
        # The old single-band keys are still honoured so a tuned booth keeps
        # working untouched: under that scheme every accepted read both showed
        # and opened, so rssi_filter maps to both lower bounds.
        legacy_min = cfg.get('scanner', 'rssi_filter',     fallback='0')
        legacy_max = cfg.get('scanner', 'rssi_filter_max', fallback='0')
        rssi_detect   = float(cfg.get('scanner', 'rssi_detect',   fallback=legacy_min))
        rssi_open_min = float(cfg.get('scanner', 'rssi_open_min', fallback=legacy_min))
        rssi_open_max = float(cfg.get('scanner', 'rssi_open_max', fallback=legacy_max))
        rssi_window     = int(cfg.get('scanner', 'rssi_window',      fallback='5'))
        rssi_hysteresis = float(cfg.get('scanner', 'rssi_hysteresis', fallback='3.0'))
        serial_port = cfg.get('barrier', 'port',       fallback='/dev/ttyUSB0')
        serial_baud = int(cfg.get('barrier', 'baudrate', fallback='115200'))
        open_secs   = float(cfg.get('barrier', 'open_seconds', fallback='2.0'))
        # Booths running qtserver-v2-new let its barrierServer own the serial
        # port; the gate asks it over HTTP instead of writing to the same tty.
        # Detected at startup, so no booth needs its config edited for this.
        barrier_service_url = cfg.get(
            'barrier', 'service_url', fallback=barrier_mod.DEFAULT_SERVICE_URL)
        barrier_service_cycle = float(
            cfg.get('barrier', 'service_cycle_seconds', fallback='0.5'))
        # 'serial' pins the old behaviour on a booth where the service must not
        # be used; anything else auto-detects.
        barrier_mode = cfg.get('barrier', 'mode', fallback='auto').strip().lower()
        display_ip  = cfg.get('display', 'display_ip', fallback='192.168.78.12')
        # A gate query is always a point lookup. 10s is far beyond anything
        # healthy and far below master's own 15-minute ceiling. 0 disables.
        statement_timeout_ms = int(
            cfg.get('gate', 'statement_timeout_ms', fallback='10000'))

        if gate_mode not in ('entry', 'exit'):
            raise CommandError(f"Invalid gate mode '{gate_mode}' — must be 'entry' or 'exit'.")

        if rssi_window < 1:
            raise CommandError(f"rssi_window must be >= 1, got {rssi_window}.")
        if rssi_hysteresis < 0:
            raise CommandError(f"rssi_hysteresis must be >= 0, got {rssi_hysteresis}.")
        if rssi_open_min and rssi_open_max and rssi_open_min > rssi_open_max:
            raise CommandError(
                f"rssi_open_min ({rssi_open_min:g}) is above rssi_open_max "
                f"({rssi_open_max:g}) — the barrier could never open."
            )
        # A vehicle has to be noticed before it can be let through. If the detect
        # threshold sits inside the open band, a tag reaches the barrier stage
        # without ever having been detected — survivable, but it means the UFD
        # never shows a balance and the operator has mistuned the lane.
        if rssi_detect and rssi_open_min and rssi_detect > rssi_open_min:
            raise CommandError(
                f"rssi_detect ({rssi_detect:g}) is above rssi_open_min "
                f"({rssi_open_min:g}) — a vehicle would reach the barrier band "
                f"before the gate ever noticed it. Detect must be the weaker "
                f"(more negative) threshold."
            )

        # This booth's mode is still declared twice — `mode` here in
        # rfid_config.ini and GATE_MODE in .env — but only the former decides
        # anything now. GATE_MODE used to select which passes mtag-sync ran, and
        # that process is gone, so a disagreement between the two is a tidiness
        # problem rather than a lane that turns paying vehicles away. Said once,
        # quietly, instead of the old three-line alarm.
        from django.conf import settings
        env_mode = str(getattr(settings, 'GATE_MODE', '') or '').strip().lower()
        if env_mode and env_mode != gate_mode:
            self.stdout.write(self.style.WARNING(
                f"[gate] .env GATE_MODE='{env_mode}' disagrees with "
                f"rfid_config.ini mode='{gate_mode}'. The gate follows "
                f"rfid_config.ini; GATE_MODE is no longer read by anything. "
                f"Align .env when convenient."
            ))

        if statement_timeout_ms > 0:
            install_statement_timeout(statement_timeout_ms, self.stdout)

        test_mode = options['test_mode']

        if test_mode:
            self.stdout.write(self.style.WARNING(
                "[TEST MODE] DB checks DISABLED — barrier will open for every scan"
            ))
        else:
            plaza_row_id, lane_id = resolve_plaza_lane(plaza_id, plaza_row_id, lane_number, lane_id)

        self.stdout.write(self.style.SUCCESS(
            f"[gate] Mode: {gate_mode.upper()} | Plaza: {plaza_id or 'TEST'} "
            f"({plaza_row_id or 'TEST'}) | Lane: {lane_id or 'unset'}"
        ))

        gate = GateController(
            gate_mode=gate_mode,
            plaza_id=plaza_row_id,
            lane_id=lane_id,
            serial_port=serial_port,
            serial_baud=serial_baud,
            open_secs=open_secs,
            barrier_service_url=barrier_service_url,
            barrier_service_cycle=barrier_service_cycle,
            barrier_mode=barrier_mode,
            display_ip=display_ip,
            tag_cooldown=tag_cooldown,
            antenna_power=antenna_power,
            rssi_detect=rssi_detect,
            rssi_open_min=rssi_open_min,
            rssi_open_max=rssi_open_max,
            rssi_window=rssi_window,
            rssi_hysteresis=rssi_hysteresis,
            test_mode=test_mode,
            stdout=self.stdout,
            style=self.style,
        )

        gate.run(reader_host, reader_port, scan_interval)


# ── Display helper ────────────────────────────────────────────────────────────

def _fire(url):
    """Fire-and-forget HTTP GET for display / indicator URLs."""
    import requests
    try:
        requests.get(url, timeout=2)
    except Exception:
        pass  # display is optional hardware — silently ignore failures


def _bg_display(url):
    threading.Thread(target=_fire, args=(url,), daemon=True).start()


# ── Gate controller ───────────────────────────────────────────────────────────

class GateController:
    def __init__(
        self, *, gate_mode, plaza_id, lane_id,
        serial_port, serial_baud, open_secs,
        display_ip, tag_cooldown, stdout,
        antenna_power=33, rssi_detect=0, rssi_open_min=0, rssi_open_max=0,
        rssi_window=5, rssi_hysteresis=3.0, test_mode=False,
        barrier_service_url=barrier_mod.DEFAULT_SERVICE_URL,
        barrier_service_cycle=0.5, barrier_mode='auto', style=None,
        record_activity=True,
    ):
        self.gate_mode     = gate_mode
        self.plaza_id      = plaza_id
        self.lane_id       = lane_id
        self.open_secs     = open_secs
        self.display_ip    = display_ip
        self.tag_cooldown  = tag_cooldown
        self.antenna_power = antenna_power
        self.rssi_detect     = rssi_detect
        self.rssi_open_min   = rssi_open_min
        self.rssi_open_max   = rssi_open_max
        self.rssi_window     = rssi_window
        self.rssi_hysteresis = rssi_hysteresis
        self.test_mode       = test_mode
        self.stdout        = stdout
        # run() reports a reader that refuses extended TID reads via
        # self.style.ERROR. GateController never had a `style`, so that branch
        # raised AttributeError instead of printing the warning — crashing the
        # command at the one moment it was trying to explain itself, and leaving
        # PM2 to restart straight back into the same rejection until it gave up
        # on the lane. no_style() returns the text unchanged, so a caller that
        # passes no style still gets the message.
        self.style         = style or no_style()

        # RSSI smoothing state (see _rssi_stage) — one short window per tag.
        self._rssi_hist: dict    = {}   # tid → deque[float]
        self._rssi_at_barrier: dict = {}  # tid → bool (in the open band, for hysteresis)
        self._rssi_stage_last: dict = {}  # tid → str (last stage, to log only changes)
        self._balance_shown: dict   = {}  # tid → float (monotonic) — UFD throttle
        self._rssi_seen: dict    = {}   # tid → float (monotonic) — for pruning
        self._rssi_lock          = threading.Lock()
        self._rssi_pruned: float = 0.0  # monotonic time of last prune

        self.last_seen: dict      = {}   # (epc, tid) → datetime
        self.last_trigger: dict   = {}   # tid → float (monotonic)
        self._recent_ok: dict     = {}   # tid → float (monotonic) — recently processed tags
        self._tag_state_pruned: float = 0.0  # monotonic time of last prune
        self._last_tx: float      = 0.0  # monotonic time of last transaction
        # Which transaction the idle greeting was last sent for, and when — so
        # a quiet lane is not repainted every scan. -1.0 so the first call sends.
        self._welcome_tx: float   = -1.0
        self._welcome_at: float   = 0.0
        # The barrier is open from now until _open_until (monotonic). Every
        # approved vehicle pushes that deadline out instead of queueing its own
        # opening — see _hold_open_for_vehicle.
        self._open_until: float   = 0.0
        # When the current continuous opening began — the datum MAX_CONTINUOUS_OPEN
        # is measured from.
        self._open_started: float = 0.0
        self._barrier_open        = False
        self._lock = threading.Lock()
        self._running = True

        # Every read, decision and barrier command also goes to the local
        # activity file, which is what the booth console at /booth/ draws. It is
        # queue-backed and swallows its own errors, so nothing here can stall a
        # lane — see apps/tolls/booth_activity.py. Tests construct controllers in
        # bulk and want neither the thread nor the file, hence the switch.
        self.activity = (
            booth_activity.get_recorder() if record_activity
            else booth_activity.NullRecorder()
        )

        self.barrier = barrier_mod.BarrierBackend(
            serial_port=serial_port, serial_baud=serial_baud,
            open_secs=open_secs, stdout=stdout,
            service_url=barrier_service_url,
            service_cycle_secs=barrier_service_cycle,
            prefer_service=(barrier_mode != 'serial'),
        )

        # Start portal-triggered gate open polling thread
        threading.Thread(target=self._poll_portal_opens, daemon=True).start()

    # ── Portal-triggered gate opens ───────────────────────────────────────────

    def _poll_portal_opens(self):
        """Poll DB every second for gate opens triggered via the admin portal."""
        if not self.plaza_id:
            return  # no plaza_id in test mode — skip polling

        from datetime import timedelta
        from django.utils import timezone
        from apps.tolls.models import PendingGateOpen

        def _claim_next():
            cutoff = timezone.now() - timedelta(seconds=30)
            cmd = PendingGateOpen.objects.filter(
                plaza_id=self.plaza_id,
                executed_at__isnull=True,
                created_at__gte=cutoff,
            ).first()
            if cmd:
                cmd.executed_at = timezone.now()
                cmd.save(update_fields=['executed_at'])
            return cmd

        while self._running:
            try:
                cmd = db_call(_claim_next)
                if cmd:
                    self.stdout.write("[portal] Gate open triggered via portal")
                    self._hold_open_for_vehicle(
                        {'gateEventId': cmd.id}, source='manual')
            except Exception as exc:
                # This ran every second on the same connection for the life of
                # the process, so one dropped socket used to mean the portal
                # button never worked again either. db_call reconnects; this
                # catch is now only for the errors a reconnect cannot fix.
                self.stdout.write(f"[poll] Error: {exc}")
            time.sleep(1)

    # ── Barrier ───────────────────────────────────────────────────────────────

    def _hold_open_for_vehicle(self, metadata=None, source='rfid'):
        """Keep the barrier up long enough for one more approved vehicle.

        A convoy is one opening, not one pulse per car. Pulsing per car is what
        stranded the fourth vehicle: its tag was read far-field, charged, and
        cycled on the queue's schedule while the car was still upstream, so it
        arrived at a barrier that had already opened and closed for it.

        So every approval pushes out a shared deadline rather than waiting for
        its own turn. The first one raises the boom; the rest only extend it;
        one watcher drops it once the deadline passes with nobody new arriving.
        """
        now = time.monotonic()
        with self._lock:
            first = not self._barrier_open
            if first:
                self._barrier_open = True
                self._open_started = now
            # A vehicle approved now needs open_seconds from now, but never less
            # than what an earlier vehicle already bought.
            deadline = max(self._open_until, now + self.open_secs)
            # A stream of reads must not be able to pin the boom up: past this,
            # the lane needs a human, not a longer timer.
            #
            # The ceiling is measured from when THIS opening began, not from
            # now. Against `now` it could never bind — every extension moved the
            # ceiling forward by exactly as much as it moved the deadline, so
            # the documented 60s limit did not exist and a lane could stay open
            # indefinitely.
            ceiling = self._open_started + MAX_CONTINUOUS_OPEN
            self._open_until = min(deadline, ceiling)
            capped = deadline > ceiling
            held = self._open_until - now

        if capped:
            self.stdout.write(self.style.WARNING(
                f"[barrier] Open {MAX_CONTINUOUS_OPEN:.0f}s continuously — "
                f"refusing to extend further; the boom will drop. A lane open "
                f"this long is a fault, not a convoy."
            ))

        if not first:
            self.stdout.write(f"[barrier] EXTENDING open window — {held:.1f}s left")
            self.activity.record_barrier(
                action='extend', source=source, backend=self.barrier.mode,
                ok=True, detail=f"{held:.1f}s left",
            )
            return True

        self.stdout.write(f"[barrier] HOLDING OPEN ({self.barrier.mode}) — {held:.1f}s")
        meta = {'lane': self.lane_id, 'mode': self.gate_mode}
        meta.update(metadata or {})
        ok = self.barrier.hold(meta, source=source)
        self.activity.record_barrier(
            action='hold', source=source, backend=self.barrier.mode, ok=ok,
            detail=(metadata or {}).get('plate') or (metadata or {}).get('tagId') or '',
        )
        threading.Thread(target=self._release_when_clear, daemon=True).start()
        return ok

    def _release_when_clear(self):
        """Drop the barrier once the last approved vehicle's window expires.

        Polls rather than sleeping the whole window in one go, because the
        deadline moves: a car approved while this is waiting extends it, and the
        boom has to stay up for it.
        """
        while True:
            with self._lock:
                remaining = self._open_until - time.monotonic()
                if remaining <= 0 or not self._running:
                    # Deciding to drop the boom and recording that it is down
                    # MUST happen under one acquisition of the lock. When they
                    # were split, a vehicle approved in the gap was told its
                    # window had been extended — and was then released anyway,
                    # with its deadline wiped to zero. That car had already been
                    # charged, its tag was suppressed as 'already cleared', and
                    # nothing was left to raise the boom for it.
                    self._barrier_open = False
                    self._open_until = 0.0
                    break
            time.sleep(min(remaining, 0.2))

        self.stdout.write("[barrier] RELEASING")
        ok = self.barrier.release()
        self.activity.record_barrier(
            action='release', source='gate', backend=self.barrier.mode, ok=ok)
        return ok

    # ── Display ───────────────────────────────────────────────────────────────

    def _show_fare(self, fare):
        _bg_display(f"http://{self.display_ip}/?vehicle_number=Q.TAG&fare_amount={fare}")

    def _show_balance(self, balance):
        """The only thing the customer-facing display ever states: what is left.

        Refusals are deliberately not shown. A driver at the barrier can do
        nothing with the word DENIED, and it reads as an accusation in front of
        whoever is behind them; the balance is the fact that actually explains
        the barrier and tells them what to do about it. Operators still get the
        reason — every refusal is logged as `[gate] DENIED — <reason>`.
        """
        bal = int(float(balance)) if balance else 0
        _bg_display(f"http://{self.display_ip}/?vehicle_number=R.BAL{bal}&fare_amount=0")

    def _show_denied(self, plate='', balance=None):
        # Kept so run_anpr_gate.py's call sites keep working. When the refusal
        # carries no balance (unregistered plate, no account, unknown tag) there
        # is nothing truthful to show, so the display is left as it was rather
        # than asserting a balance of 0 for an account that does not exist.
        if balance is None:
            return
        self._show_balance(balance)

    def _show_low_balance(self, current_balance, plate=''):
        self._show_balance(current_balance)

    def _show_entry(self, balance, plate=''):
        self._show_balance(balance)

    def _show_exit(self, charge, remaining, plate=''):
        rem = int(float(remaining)) if remaining else 0
        _bg_display(f"http://{self.display_ip}/?vehicle_number=R.BAL{rem}&fare_amount={charge}")

    def _show_welcome(self):
        """Put the idle greeting up — once per quiet spell, not once a second.

        The scan loop asks for this on every pass where the lane has been quiet
        longer than DISPLAY_HOLD. With scan_interval at 1s that meant a thread
        and an HTTP request every second for as long as no vehicle came, all of
        them painting a display that was already showing WELCOME: around 86,000
        requests a day at a booth, aimed at a small embedded device that has
        better things to do.

        The greeting only needs sending when something else was on the display,
        so it is sent once per transaction and then left alone. It is still
        refreshed occasionally, because the display can be power-cycled
        independently of the gate and would otherwise come back blank and stay
        that way.
        """
        gate = self
        now_m = time.monotonic()
        with self._lock:
            if (self._welcome_tx == self._last_tx
                    and now_m - self._welcome_at < WELCOME_REFRESH_SECONDS):
                return
            self._welcome_tx = self._last_tx
            self._welcome_at = now_m

        def _do():
            if time.monotonic() - gate._last_tx >= 5.0:
                _fire(f"http://{gate.display_ip}/?vehicle_number=WELCOME&take_slip")
        threading.Thread(target=_do, daemon=True).start()

    # ── RSSI gating ───────────────────────────────────────────────────────────

    def _rssi_stage(self, tid: str, rssi: float) -> str:
        """Which stage of the lane this read puts the tag in.

            'ignore'  weaker than rssi_detect — not here yet, or another lane
            'detect'  in range: show the balance, charge nothing, stay shut
            'open'    inside [rssi_open_min, rssi_open_max] — at the barrier

        Splitting these is what stops a car being charged for a barrier cycle it
        never got. The reader sees a tag many metres out; acting on that read
        opened and closed the boom while the vehicle was still approaching, and
        in a convoy it spent one car's opening on another car's tag.

        A parked vehicle does not give a steady RSSI: multipath (including our
        own barrier boom swinging through the beam), the reader's frequency
        hopping, and the SDK's coarse RSSI encoding together move a stationary
        tag by a few dB between consecutive reads. That encoding is a 3-bit
        mantissa + 5-bit exponent (Tag_Model.RSSI()), so around -55 dBm the
        representable values are only 0.6-1.0 dB apart and a drifting reading
        visibly steps between rungs.

        Comparing a single raw read against a hard threshold therefore makes a
        tag parked near a boundary flap between stages on consecutive reads — an
        intermittent gate fault that is painful to reproduce. Two things prevent
        that:

          * decide on the *median* of a short per-tag window, so one outlier
            read cannot flip the stage; and
          * apply hysteresis to the open band, so a tag already at the barrier
            has to fall `rssi_hysteresis` dB clear of it before it is let go.

        The median is taken over whatever samples exist so far, so a tag's first
        read still decides immediately — smoothing costs no gate latency.
        """
        banded = bool(self.rssi_open_min or self.rssi_open_max)
        if not self.rssi_detect and not banded:
            return 'open'  # filtering disabled — every read opens, as before

        now = time.monotonic()
        with self._rssi_lock:
            self._prune_rssi(now)

            hist = self._rssi_hist.get(tid)
            if hist is None:
                hist = self._rssi_hist[tid] = deque(maxlen=self.rssi_window)
            hist.append(rssi)
            self._rssi_seen[tid] = now
            level = statistics.median(hist)
            samples = len(hist)

            if self.rssi_detect and level < self.rssi_detect:
                stage = 'ignore'
            elif not banded:
                # A detect threshold on its own means the old behaviour above it.
                stage = 'open'
            else:
                # Hysteresis only widens the band for a tag already inside it, so
                # a newcomer must clear the configured band outright.
                slack = self.rssi_hysteresis if self._rssi_at_barrier.get(tid) else 0.0
                below = self.rssi_open_min and level < self.rssi_open_min - slack
                above = self.rssi_open_max and level > self.rssi_open_max + slack
                stage = 'detect' if (below or above) else 'open'

            self._rssi_at_barrier[tid] = stage == 'open'
            changed = self._rssi_stage_last.get(tid) != stage
            self._rssi_stage_last[tid] = stage

        # Log only on a stage change, so a car sitting in the field does not
        # flood the log with one identical line per read.
        if changed:
            self.stdout.write(
                f"[rssi] {tid} → {stage.upper()} at {level:.1f} dBm "
                f"(median of {samples})"
            )
        return stage

    def _rssi_snapshot(self, tid: str, rssi: float):
        """The level the gate just decided on, and how many reads it came from.

        `_rssi_stage` keeps this in `_rssi_hist`, but it returns only the stage —
        and its return type is what the staging tests assert on, so it stays a
        plain string. Peeking at the window afterwards gets the console the
        median without changing that contract.

        With filtering off the window is never populated, so the raw read is the
        level and it stands on its own.
        """
        with self._rssi_lock:
            hist = self._rssi_hist.get(tid)
            if not hist:
                return rssi, 1
            return statistics.median(hist), len(hist)

    def _prune_tag_state(self, now_dt):
        """Drop per-tag bookkeeping for vehicles long gone. Caller holds _lock.

        _prune_rssi already did this for the RSSI windows, but the three dicts
        guarded by _lock were never pruned at all: last_seen gained an entry per
        (EPC, TID) ever seen, last_trigger and _recent_ok one per TID. On a lane
        passing thousands of distinct vehicles a day that is a process which
        only ever grows — the gate is meant to run for months between restarts,
        and the one thing it must not do is slowly consume the booth.

        Entries are only useful for as long as the windows that read them: the
        1-second dedup, the per-tag cooldown, and the open_secs + 2s clearance
        grace. Anything older than the longest of those, with margin, cannot
        change a decision.
        """
        now_m = time.monotonic()
        if now_m - self._tag_state_pruned < 60.0:
            return
        self._tag_state_pruned = now_m

        ttl = max(60.0, self.tag_cooldown * 4, self.open_secs + 2.0)
        for tid in [t for t, seen in self.last_trigger.items() if now_m - seen > ttl]:
            del self.last_trigger[tid]
        for tid in [t for t, seen in self._recent_ok.items() if now_m - seen > ttl]:
            del self._recent_ok[tid]
        cutoff = now_dt - timedelta(seconds=ttl)
        for key in [k for k, seen in self.last_seen.items() if seen < cutoff]:
            del self.last_seen[key]

    def _prune_rssi(self, now: float):
        """Drop windows for tags long gone. Caller must hold _rssi_lock."""
        if now - self._rssi_pruned < 30.0:
            return
        self._rssi_pruned = now
        ttl = max(60.0, self.tag_cooldown * 4)
        for tid in [t for t, seen in self._rssi_seen.items() if now - seen > ttl]:
            self._rssi_hist.pop(tid, None)
            self._rssi_at_barrier.pop(tid, None)
            self._rssi_stage_last.pop(tid, None)
            self._balance_shown.pop(tid, None)
            self._rssi_seen.pop(tid, None)

    # ── Tag processing ────────────────────────────────────────────────────────

    def _process_tag(self, tag_serial: str) -> dict:
        from apps.tolls.services import EntryService, ExitService
        if self.gate_mode == 'entry':
            return db_call(
                EntryService.process_entry, tag_serial, self.plaza_id, self.lane_id)
        return db_call(
            ExitService.process_exit, tag_serial, self.plaza_id, self.lane_id)

    def on_tag(self, epc: str, tid: str, rssi: float = 0.0):
        """Route one read to its stage. Nothing here costs the customer money.

        The reader sees a tag long before the vehicle reaches the boom, so a read
        on its own is not an arrival. Far-field reads only tell the driver what
        their balance is; the trip is charged, and the barrier opened, in
        _at_barrier — when the signal says the vehicle is actually there.
        """
        stage = self._rssi_stage(tid, rssi)
        # Recorded BEFORE the 'ignore' return and before the 1-second dedup
        # below, so the console shows every read the reader actually reported.
        # A tag sitting too far out to act on is precisely what someone tuning
        # rssi_detect needs to see; a history of only the reads that passed
        # would answer the question by assuming it.
        median, samples = self._rssi_snapshot(tid, rssi)
        self.activity.record_read(
            epc=epc, tid=tid, rssi=rssi, median=median,
            samples=samples, stage=stage,
        )
        if stage == 'ignore':
            return

        now = datetime.now()
        key = (epc, tid)
        with self._lock:
            self._prune_tag_state(now)
            # 1-second deduplication. Cheap, and applies to both stages — the
            # reader reports the same tag several times per inventory pass.
            prev = self.last_seen.get(key)
            if prev and (now - prev).total_seconds() <= 1:
                return
            self.last_seen[key] = now

        if stage == 'detect':
            self._approaching(tid)
            return
        self._at_barrier(epc, tid, now)

    # ── Stage 1: in range, not yet at the barrier ────────────────────────────

    def _approaching(self, tid: str):
        """Show this tag's balance. No trip, no charge, no barrier.

        Runs on every read of every tag in range, so it is throttled per tag and
        goes through the read-only preview rather than the charging services.
        """
        now_m = time.monotonic()
        with self._lock:
            # A vehicle already cleared at the barrier is on its way through;
            # re-announcing its pre-charge balance would contradict the figure
            # the UFD is showing it.
            if tid in self._recent_ok:
                return
            last = self._balance_shown.get(tid)
            if last is not None and (now_m - last) < BALANCE_REFRESH_SECONDS:
                return
            self._balance_shown[tid] = now_m

        from apps.tolls.services import preview_tag
        preview = db_call(preview_tag, tid)
        if not preview.get('success'):
            # Not shown to the driver — see _show_balance on why refusals stay
            # off the UFD. The operator still gets it, once per approach.
            self.stdout.write(
                f"[gate] In range, not chargeable — {preview.get('reason')} ({tid})")
            self.activity.record_gate_event(
                kind='preview', tid=tid, result='denied',
                reason=preview.get('reason', ''),
            )
            return

        balance = preview.get('current_balance', '0')
        short = "" if preview.get('sufficient') else " [BELOW MINIMUM]"
        self.stdout.write(
            f"[gate] In range — {preview.get('vehicle')} "
            f"balance: Rs.{balance}{short}"
        )
        self._last_tx = time.monotonic()
        self.activity.record_gate_event(
            kind='preview', tid=tid, plate=preview.get('vehicle', ''),
            result='ok', balance=balance,
            reason='' if preview.get('sufficient') else 'below minimum',
        )
        self._show_balance(balance)

    # ── Stage 2: at the barrier — charge, then open ──────────────────────────

    def _at_barrier(self, epc: str, tid: str, now):
        with self._lock:
            now_m = time.monotonic()

            # An already-cleared tag stays suppressed for as long as the barrier
            # is actually up: during a convoy that window keeps being extended,
            # and re-processing a car still sitting in the field would charge it
            # a second time. Once the boom drops, the entry expires on its own
            # grace and the tag must go through the DB again.
            recent = self._recent_ok.get(tid)
            if recent is not None:
                if self._barrier_open or (now_m - recent) < (self.open_secs + 2.0):
                    self.stdout.write(
                        f"[gate] Already cleared this approach — skipping {tid}")
                    return
                del self._recent_ok[tid]

            # Per-tag cooldown (only for tags not yet processed)
            last_t = self.last_trigger.get(tid)
            if last_t and (now_m - last_t) < self.tag_cooldown:
                remaining = self.tag_cooldown - (now_m - last_t)
                self.stdout.write(f"[cooldown] {tid} — wait {remaining:.1f}s")
                return
            self.last_trigger[tid] = now_m

        self.stdout.write(f"\n>>> AT BARRIER | EPC: {epc} | TID: {tid} | {now} | mode={self.gate_mode.upper()}")

        # Test mode: skip all DB checks, open barrier immediately
        if self.test_mode:
            self.stdout.write(f"[TEST] Tag at barrier — opening (DB check skipped)")
            self._last_tx = time.monotonic()
            self.activity.record_gate_event(
                kind='test', tid=tid, epc=epc, result='ok',
                reason='test mode — no DB check',
            )
            self._hold_open_for_vehicle({'tagId': tid, 'testMode': True})
            return

        # This is the charge. It happens here and nowhere else, so a vehicle
        # only ever pays for an opening it was present for.
        result = self._process_tag(tid)

        plate = result.get('vehicle', '')
        if not result.get('success'):
            reason = result.get('reason', 'denied')
            self.stdout.write(f"[gate] DENIED — {reason}")
            self._last_tx = time.monotonic()
            self.activity.record_gate_event(
                kind=self.gate_mode, tid=tid, epc=epc, plate=plate,
                result='denied', reason=reason,
                balance=result.get('current_balance', ''),
            )
            # Pass the balance through when the refusal carries one, so the
            # display can still show it. Absent (unknown tag, no account), it
            # stays None and the display is left untouched.
            self._show_denied(plate, result.get('current_balance'))
            return

        offline_flag = " [OFFLINE]" if result.get('offline') else ""
        self._last_tx = time.monotonic()
        with self._lock:
            self._recent_ok[tid] = time.monotonic()

        if self.gate_mode == 'exit':
            self.stdout.write(
                f"[gate] EXIT OK{offline_flag} — vehicle: {result.get('vehicle')} "
                f"charge: Rs.{result.get('charge')} "
                f"balance: Rs.{result.get('balance_remaining')}"
            )
            self.activity.record_gate_event(
                kind='exit', tid=tid, epc=epc, plate=plate, result='ok',
                charge=result.get('charge', ''),
                balance=result.get('balance_remaining', ''),
                offline=bool(result.get('offline')),
            )

            def display_fn():
                self._show_exit(result.get('charge', '0'), result.get('balance_remaining', '0'), plate)
        else:
            self.stdout.write(
                f"[gate] ENTRY OK{offline_flag} — vehicle: {result.get('vehicle')} "
                f"balance: Rs.{result.get('current_balance')}"
            )
            self.activity.record_gate_event(
                kind='entry', tid=tid, epc=epc, plate=plate, result='ok',
                balance=result.get('current_balance', ''),
                offline=bool(result.get('offline')),
            )

            def display_fn():
                self._show_entry(result.get('current_balance', '0'), plate)

        display_fn()
        self._hold_open_for_vehicle({'tagId': tid, 'plate': plate})

    # ── Empty TID guard ───────────────────────────────────────────────────────

    def on_tag_empty_tid(self, epc: str):
        self.stdout.write(f"[warn] Tag scanned but TID is empty (EPC={epc or 'none'}) — check extended-read config")

    # ── RFID reader loop ──────────────────────────────────────────────────────

    def run(self, reader_host: str, reader_port: int, scan_interval: float = 1.0):
        try:
            from com.rfid.Reader import Reader
            from com.rfid.enumeration import EReaderEnum, EReadBank, EReaderResult
            from com.rfid.models import ReadExtendedArea_Model
            from com.rfid.interface import IAsynchronousMessage
        except ImportError:
            raise CommandError(
                "com.rfid SDK not found. Install or add the SDK directory to PYTHONPATH.\n"
                "The SDK JAR/wheel should be placed alongside manage.py."
            )

        gate = self

        class _Listener(IAsynchronousMessage):
            def OutputTags(self, tag):
                try:
                    epc = getattr(tag, '_EPC', '') or ''
                    tid_raw = getattr(tag, '_TID', '') or ''
                    tid = tid_raw.replace(' ', '').upper()
                    if not tid:
                        gate.on_tag_empty_tid(epc)
                        return
                    # Staging (and its logging) happens in on_tag, which needs
                    # the raw reading to decide. Logging every read here as well
                    # buried the stage changes that actually matter.
                    gate.on_tag(epc, tid, tag.RSSI())
                except Exception as exc:
                    # This catch exists so one bad read cannot kill the SDK's
                    # receive thread and with it the whole lane. But a bare
                    # message is what made the stale-connection fault so hard to
                    # find: the barrier silently stopped opening and the log said
                    # only "[error] OutputTags: ...". Anything landing here is a
                    # vehicle that was not let through, so log it as an error
                    # with the traceback that names the real cause.
                    gate.stdout.write(f"[error] OutputTags — tag NOT processed: {exc}")
                    log.exception("[gate] unhandled error processing tag %s", tid)

            def OutputTagsOver(self, conn_id):
                pass

            def WriteDebugMsg(self, conn_id, msg):
                pass

            def WriteLog(self, conn_id, msg):
                pass

            def PortConnecting(self, conn_id):
                gate.stdout.write(f"[reader] Device connected: {conn_id}")

            def PortClosing(self, conn_id):
                gate.stdout.write(f"[reader] Device disconnected: {conn_id}")

            def GPIControlMsg(self, conn_id, gpi_model):
                pass

            def OutputScanData(self, conn_id, scandata):
                pass

        self._show_welcome()

        tcp = f"TCP:{reader_host}:{reader_port}"
        DISPLAY_HOLD = 5.0
        RECONNECT_DELAY = 5  # seconds between reconnect attempts
        MAX_CONSECUTIVE_FAILURES = 3

        # The SDK keeps a process-wide registry of open connections keyed by
        # "host:port", and CreateTcpConn REFUSES outright — without so much as
        # attempting a socket — if the endpoint is already in it. Dropping a
        # Reader without closing it therefore does not just leak its two
        # non-daemon threads; it makes every future reconnect to that same
        # reader impossible. The gate would sit in "Cannot connect — retrying in
        # 5s" for ever against a reader that was perfectly healthy, and only a
        # process restart cleared it.
        #
        # The registry is only self-cleaning when the socket itself raises:
        # rcvThread's handler calls CloseConn on the way out. An inventory loop
        # that fails for any other reason (a wedged reader, an antenna fault, a
        # desynced protocol stream) leaves the entry behind — which is exactly
        # the path that breaks out of the loop below.
        reader = None

        def _drop_reader():
            """Release the SDK registry entry so a reconnect can succeed."""
            nonlocal reader
            if reader is None:
                return
            try:
                reader.closeConnect()
            except Exception as exc:
                self.stdout.write(f"[reader] Error closing connection: {exc}")
            reader = None

        try:
            while self._running:
                _drop_reader()
                listener = _Listener()
                reader = Reader()

                if not reader.initReader(tcp, listener):
                    self.stdout.write(
                        f"[reader] Cannot connect to {tcp} — retrying in {RECONNECT_DELAY}s"
                    )
                    _drop_reader()
                    time.sleep(RECONNECT_DELAY)
                    continue

                self.stdout.write(f"[reader] Connected to {tcp}")

                # ── Reader setup — mirrors the proven rfid_final_2.py sequence ──
                # rfid_final_2.py reads TID reliably and does NOT set antenna
                # power; it relies on the reader's own saved power and simply
                # enables the extended TID read. Setting RW_RFIDAntPower (over
                # antennas 1-4) was the only configuration difference and the
                # likely reason TID dropped, so we follow the working flow:
                #   1. read reader info (SN)
                #   2. enable extended TID read
                from com.rfid.models.ReaderInfo_Model import ReaderInfo_Model
                reader_info = ReaderInfo_Model()
                if reader.paramGet(EReaderEnum.RO_ReaderInformation, reader_info) == EReaderResult.RT_OK:
                    self.stdout.write(f"[reader] SN: {reader_info.readerSN}")

                # Enable extended TID read. Without this the reader only uploads
                # EPC and tag._TID stays empty. Capture the result — if the
                # reader rejects it, TID will silently never appear.
                tid_result = reader.paramSet(
                    EReaderEnum.WO_RFIDReadExtended,
                    [ReadExtendedArea_Model(EReadBank.TID, 0, 6, "")]
                )
                if tid_result == EReaderResult.RT_OK:
                    self.stdout.write("[reader] Extended TID read ENABLED (result=RT_OK)")
                else:
                    self.stdout.write(self.style.ERROR(
                        f"[reader] Extended TID read REJECTED (result={tid_result}) — "
                        f"tags will report EPC only. Check reader firmware / TID support."
                    ))

                consecutive_failures = 0
                scan_count = 0
                while self._running:
                    if time.monotonic() - self._last_tx > DISPLAY_HOLD:
                        self._show_welcome()
                    if scan_count % 10 == 0:
                        self.stdout.write("[reader] Scanning...")
                    scan_count += 1
                    result = reader.inventory()
                    if result not in (EReaderResult.RT_OK, EReaderResult.RT_TIMEOUT_ERR):
                        consecutive_failures += 1
                        self.stdout.write(
                            f"[reader] inventory error ({result}) — "
                            f"attempt {consecutive_failures}/{MAX_CONSECUTIVE_FAILURES}"
                        )
                        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                            self.stdout.write(
                                f"[reader] Connection lost — reconnecting in {RECONNECT_DELAY}s"
                            )
                            time.sleep(RECONNECT_DELAY)
                            break
                    else:
                        consecutive_failures = 0
                    time.sleep(scan_interval)

        except KeyboardInterrupt:
            self.stdout.write("\n[gate] Interrupted — shutting down")
        finally:
            self._running = False
            # Clears _IsConnect/_IsStartReceive, which is what the SDK's receive
            # thread loops on. Without it those non-daemon threads keep the
            # interpreter alive and PM2 has to SIGKILL the process.
            _drop_reader()
            # A held barrier has no timer of its own — the watcher that would
            # drop it is stopping too. Release explicitly, and before cleanup,
            # so it is queued ahead of the worker's shutdown sentinel.
            if self._barrier_open:
                self.stdout.write("[barrier] RELEASING — gate shutting down")
                self._barrier_open = False
                self._open_until = 0.0
                self.barrier.release()
            self.barrier.cleanup()
            # Last, so the release above is recorded before the writer stops.
            self.activity.close()

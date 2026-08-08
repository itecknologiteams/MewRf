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
import threading
import time
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

log = logging.getLogger('apps.tolls.gate')


def resolve_plaza_lane(plaza_id: str, plaza_uuid: str, lane_number: str, lane_id: str):
    """Resolve config's plaza_id/lane_number to the DB UUIDs the gate needs.

    `plaza_id` is the operator-assigned plaza number from Plaza.plaza_id (this
    replaced the old `plaza_code`). `plaza_uuid` is the raw Plaza.id escape
    hatch, used only when plaza_id is not set.

    Returns (plaza_uuid, lane_id) — GateController addresses rows by UUID.
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
            "(e.g. plaza_id = 3). Use the plaza_uuid key if you really do want to "
            "pin this booth to a raw Plaza.id."
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
            plaza_uuid = str(Plaza.objects.get(plaza_id=number).id)
        except Plaza.DoesNotExist:
            raise CommandError(
                f"Plaza with plaza_id {number} not found in DB.\n"
                f"Available plaza_ids: {_available()}"
            )
    elif not plaza_uuid or plaza_uuid == '00000000-0000-0000-0000-000000000000':
        raise CommandError(
            f"Set plaza_id (e.g. plaza_id = 3) in config.\n"
            f"Available plaza_ids: {_available()}"
        )

    # Resolve lane. NB: TollLane.plaza_id is Django's FK column and holds the
    # Plaza UUID — it is not Plaza.plaza_id, the integer resolved above.
    if lane_number and not lane_id:
        try:
            lane = TollLane.objects.get(plaza_id=plaza_uuid, lane_number=int(lane_number))
            lane_id = str(lane.id)
        except TollLane.DoesNotExist:
            raise CommandError(
                f"Lane {lane_number} not found for plaza {plaza_id or plaza_uuid}."
            )

    return plaza_uuid, lane_id or None


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
                "tag_cooldown = 5.0\n\n"
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
        plaza_uuid  = cfg.get('gate', 'plaza_uuid', fallback='').strip()
        lane_id     = cfg.get('gate', 'lane_id',    fallback='').strip() or None
        lane_number = cfg.get('gate', 'lane_number', fallback='').strip() or None
        reader_host = cfg.get('scanner', 'reader_host', fallback='192.168.78.8')
        reader_port = int(cfg.get('scanner', 'reader_port', fallback='9090'))
        tag_cooldown    = float(cfg.get('scanner', 'tag_cooldown',    fallback='5.0'))
        antenna_power   = int(cfg.get('scanner', 'antenna_power',   fallback='33'))
        scan_interval   = float(cfg.get('scanner', 'scan_interval',  fallback='1.0'))
        rssi_filter     = int(cfg.get('scanner', 'rssi_filter',     fallback='0'))
        rssi_filter_max = int(cfg.get('scanner', 'rssi_filter_max', fallback='0'))
        serial_port = cfg.get('barrier', 'port',       fallback='/dev/ttyUSB0')
        serial_baud = int(cfg.get('barrier', 'baudrate', fallback='115200'))
        open_secs   = float(cfg.get('barrier', 'open_seconds', fallback='2.0'))
        display_ip  = cfg.get('display', 'display_ip', fallback='192.168.78.12')

        if gate_mode not in ('entry', 'exit'):
            raise CommandError(f"Invalid gate mode '{gate_mode}' — must be 'entry' or 'exit'.")

        # This booth's mode is declared twice: `mode` here in rfid_config.ini
        # (what the gate does) and GATE_MODE in .env (which sync passes mtag-sync
        # runs). booth_bootstrap.sh writes both from one value, but a hand-edit to
        # one leaves them disagreeing — and the bad case is silent: an exit lane
        # whose sync runs in entry mode never pulls open trips, so every exiting
        # vehicle is turned away with "No active trip found".
        from django.conf import settings
        sync_mode = str(getattr(settings, 'GATE_MODE', '') or '').strip().lower()
        if sync_mode and sync_mode != gate_mode:
            self.stdout.write(self.style.ERROR(
                f"!!! MODE MISMATCH: rfid_config.ini mode='{gate_mode}' but "
                f".env GATE_MODE='{sync_mode}'.\n"
                f"!!!   The gate will run as '{gate_mode}' while mtag-sync syncs as "
                f"'{sync_mode}'.\n"
                f"!!!   Fix .env to GATE_MODE={gate_mode} and restart mtag-sync."
            ))

        test_mode = options['test_mode']

        if test_mode:
            self.stdout.write(self.style.WARNING(
                "[TEST MODE] DB checks DISABLED — barrier will open for every scan"
            ))
        else:
            plaza_uuid, lane_id = resolve_plaza_lane(plaza_id, plaza_uuid, lane_number, lane_id)

        self.stdout.write(self.style.SUCCESS(
            f"[gate] Mode: {gate_mode.upper()} | Plaza: {plaza_id or 'TEST'} "
            f"({plaza_uuid or 'TEST'}) | Lane: {lane_id or 'unset'}"
        ))

        gate = GateController(
            gate_mode=gate_mode,
            plaza_id=plaza_uuid,
            lane_id=lane_id,
            serial_port=serial_port,
            serial_baud=serial_baud,
            open_secs=open_secs,
            display_ip=display_ip,
            tag_cooldown=tag_cooldown,
            antenna_power=antenna_power,
            rssi_filter=rssi_filter,
            rssi_filter_max=rssi_filter_max,
            test_mode=test_mode,
            stdout=self.stdout,
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
        antenna_power=33, rssi_filter=0, rssi_filter_max=0, test_mode=False,
    ):
        self.gate_mode     = gate_mode
        self.plaza_id      = plaza_id
        self.lane_id       = lane_id
        self.open_secs     = open_secs
        self.display_ip    = display_ip
        self.tag_cooldown  = tag_cooldown
        self.antenna_power = antenna_power
        self.rssi_filter     = rssi_filter
        self.rssi_filter_max = rssi_filter_max
        self.test_mode       = test_mode
        self.stdout        = stdout

        self.last_seen: dict      = {}   # (epc, tid) → datetime
        self.last_trigger: dict   = {}   # tid → float (monotonic)
        self._recent_ok: dict     = {}   # tid → float (monotonic) — recently processed tags
        self._last_tx: float      = 0.0  # monotonic time of last transaction
        self._barrier_busy        = False
        self._pending_queue: list = []   # approved cars waiting for barrier
        self._lock = threading.Lock()
        self._running = True

        self._serial = None
        self._setup_serial(serial_port, serial_baud)

        # Start portal-triggered gate open polling thread
        threading.Thread(target=self._poll_portal_opens, daemon=True).start()

    # ── Serial ────────────────────────────────────────────────────────────────

    def _setup_serial(self, port, baud):
        try:
            import serial
            self._serial = serial.Serial(port=port, baudrate=baud, timeout=1)
            self.stdout.write(f"[serial] Connected on {port} at {baud} baud")
        except Exception as exc:
            self.stdout.write(f"[serial] Not available ({exc}) — barrier control disabled")
            self._serial = None

    def _send_serial(self, cmd: str):
        try:
            if self._serial and self._serial.is_open:
                self._serial.write(cmd.encode())
                return True
        except Exception as exc:
            self.stdout.write(f"[serial] Write error: {exc}")
            self._serial = None
        return False

    # ── Portal-triggered gate opens ───────────────────────────────────────────

    def _poll_portal_opens(self):
        """Poll DB every second for gate opens triggered via the admin portal."""
        if not self.plaza_id:
            return  # no plaza_id in test mode — skip polling

        from datetime import timedelta
        from django.utils import timezone
        from apps.tolls.models import PendingGateOpen

        while self._running:
            try:
                cutoff = timezone.now() - timedelta(seconds=30)
                cmd = PendingGateOpen.objects.filter(
                    plaza_id=self.plaza_id,
                    executed_at__isnull=True,
                    created_at__gte=cutoff,
                ).first()
                if cmd:
                    cmd.executed_at = timezone.now()
                    cmd.save(update_fields=['executed_at'])
                    self.stdout.write("[portal] Gate open triggered via portal")
                    self._open_barrier()
                    self._schedule_close()
            except Exception as exc:
                self.stdout.write(f"[poll] Error: {exc}")
            time.sleep(1)

    # ── Barrier ───────────────────────────────────────────────────────────────

    def _open_barrier(self):
        self.stdout.write("[barrier] OPENING")
        self._send_serial('o')

    def _close_barrier(self):
        self.stdout.write("[barrier] CLOSING")
        self._send_serial('f')

    def _schedule_close(self):
        def _do():
            time.sleep(self.open_secs)
            self._close_barrier()
            # Process next car in queue
            with self._lock:
                self._barrier_busy = False
                next_item = self._pending_queue.pop(0) if self._pending_queue else None
            if next_item:
                next_tid, next_display_fn = next_item
                self.stdout.write(
                    f"[queue] Processing next car: {next_tid} "
                    f"({len(self._pending_queue)} remaining)"
                )
                with self._lock:
                    self._barrier_busy = True
                next_display_fn()
                self._open_barrier()
                self._schedule_close()
        threading.Thread(target=_do, daemon=True).start()

    # ── Display ───────────────────────────────────────────────────────────────

    def _show_fare(self, fare):
        _bg_display(f"http://{self.display_ip}/?vehicle_number=Q.TAG&fare_amount={fare}")

    def _show_denied(self, plate=''):
        _bg_display(f"http://{self.display_ip}/?vehicle_number=DENIED&fare_amount=0")

    def _show_low_balance(self, current_balance, plate=''):
        bal = int(float(current_balance)) if current_balance else 0
        _bg_display(f"http://{self.display_ip}/?vehicle_number=LOW.BAL&fare_amount={bal}")

    def _show_entry(self, balance, plate=''):
        bal = int(float(balance)) if balance else 0
        _bg_display(f"http://{self.display_ip}/?vehicle_number=R.BAL{bal}&fare_amount=0")

    def _show_exit(self, charge, remaining, plate=''):
        rem = int(float(remaining)) if remaining else 0
        _bg_display(f"http://{self.display_ip}/?vehicle_number=R.BAL{rem}&fare_amount={charge}")

    def _show_welcome(self):
        gate = self
        def _do():
            if time.monotonic() - gate._last_tx >= 5.0:
                _fire(f"http://{gate.display_ip}/?vehicle_number=WELCOME&take_slip")
        threading.Thread(target=_do, daemon=True).start()

    # ── Tag processing ────────────────────────────────────────────────────────

    def _process_tag(self, tag_serial: str) -> dict:
        from apps.tolls.services import EntryService, ExitService
        if self.gate_mode == 'entry':
            return EntryService.process_entry(tag_serial, self.plaza_id, self.lane_id)
        return ExitService.process_exit(tag_serial, self.plaza_id, self.lane_id)

    def on_tag(self, epc: str, tid: str):
        now = datetime.now()
        key = (epc, tid)

        with self._lock:
            # 1-second deduplication
            prev = self.last_seen.get(key)
            if prev and (now - prev).total_seconds() <= 1:
                return
            self.last_seen[key] = now

            now_m = time.monotonic()

            # Recently-processed check comes BEFORE cooldown so the car arriving
            # at the barrier after a far-field scan isn't blocked by the cooldown.
            # One-shot: delete after use so barrier only opens once per approach.
            # Window = open_secs + 2s grace — after that, tag must re-process via DB.
            recent = self._recent_ok.pop(tid, None)
            if recent and (now_m - recent) < (self.open_secs + 2.0):
                self.stdout.write(f"[gate] Re-scan within open window — skipping re-open for {tid}")
                return

            # Per-tag cooldown (only for tags not yet processed)
            last_t = self.last_trigger.get(tid)
            if last_t and (now_m - last_t) < self.tag_cooldown:
                remaining = self.tag_cooldown - (now_m - last_t)
                self.stdout.write(f"[cooldown] {tid} — wait {remaining:.1f}s")
                return
            self.last_trigger[tid] = now_m

        self.stdout.write(f"\n>>> EPC: {epc} | TID: {tid} | {now} | mode={self.gate_mode.upper()}")

        # Test mode: skip all DB checks, open barrier immediately
        if self.test_mode:
            self.stdout.write(f"[TEST] Tag detected — opening barrier (DB check skipped)")
            self._last_tx = time.monotonic()
            self._open_barrier()
            self._schedule_close()
            return

        result = self._process_tag(tid)

        plate = result.get('vehicle', '')
        if not result.get('success'):
            reason = result.get('reason', 'denied')
            self.stdout.write(f"[gate] DENIED — {reason}")
            self._last_tx = time.monotonic()
            if 'balance' in reason.lower() or 'insufficient' in reason.lower():
                bal = result.get('current_balance', '0')
                self._show_low_balance(bal, plate)
            else:
                self._show_denied(plate)
            return

        plate        = result.get('vehicle', '')
        offline_flag = " [OFFLINE]" if result.get('offline') else ""
        self._last_tx = time.monotonic()
        self._recent_ok[tid] = time.monotonic()

        if self.gate_mode == 'exit':
            self.stdout.write(
                f"[gate] EXIT OK{offline_flag} — vehicle: {result.get('vehicle')} "
                f"charge: Rs.{result.get('charge')} "
                f"balance: Rs.{result.get('balance_remaining')}"
            )
            def display_fn():
                self._show_exit(result.get('charge', '0'), result.get('balance_remaining', '0'), plate)
        else:
            self.stdout.write(
                f"[gate] ENTRY OK{offline_flag} — vehicle: {result.get('vehicle')} "
                f"balance: Rs.{result.get('current_balance')}"
            )
            def display_fn():
                self._show_entry(result.get('current_balance', '0'), plate)

        # Queue the barrier open — if barrier busy, car waits its turn
        with self._lock:
            if self._barrier_busy:
                self._pending_queue.append((tid, display_fn))
                self.stdout.write(
                    f"[queue] {plate} queued — position {len(self._pending_queue)}"
                )
                return
            self._barrier_busy = True

        display_fn()
        self._open_barrier()
        self._schedule_close()

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
                    rssi = tag.RSSI()
                    gate.stdout.write(f"[rssi] {tid} → {rssi:.1f} dBm")
                    if gate.rssi_filter != 0 and rssi < gate.rssi_filter:
                        gate.stdout.write(
                            f"[rssi] IGNORED — {rssi:.1f} dBm < min {gate.rssi_filter} dBm"
                        )
                        return
                    if gate.rssi_filter_max != 0 and rssi > gate.rssi_filter_max:
                        gate.stdout.write(
                            f"[rssi] IGNORED — {rssi:.1f} dBm > max {gate.rssi_filter_max} dBm"
                        )
                        return
                    gate.on_tag(epc, tid)
                except Exception as exc:
                    gate.stdout.write(f"[error] OutputTags: {exc}")

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

        try:
            while self._running:
                listener = _Listener()
                reader = Reader()

                if not reader.initReader(tcp, listener):
                    self.stdout.write(
                        f"[reader] Cannot connect to {tcp} — retrying in {RECONNECT_DELAY}s"
                    )
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
            if self._serial and self._serial.is_open:
                self._serial.close()

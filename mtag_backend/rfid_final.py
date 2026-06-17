import configparser
import time
import threading
import requests
from datetime import datetime
from com.rfid.helper import *
from com.rfid.enumeration import *
from com.rfid.Reader import *
from com.rfid.models import *
from com.rfid.interface import *

# ── Config ───────────────────────────────────────────────────────────────────
_cfg = configparser.ConfigParser()
_cfg.read('rfid_config.ini')

GATE_MODE      = _cfg.get('gate', 'mode', fallback='entry').strip().lower()  # "entry" or "exit"
PLAZA_ID       = _cfg.get('gate', 'plaza_id', fallback='').strip()
LANE_ID        = _cfg.get('gate', 'lane_id', fallback='').strip() or None

API_BASE       = _cfg.get('api', 'base_url', fallback='http://localhost:8000').rstrip('/')
OPERATOR_TOKEN = _cfg.get('api', 'operator_token', fallback='').strip()

DISPLAY_IP          = _cfg.get('display', 'display_ip', fallback='192.168.78.12')
BARRIER_SERVER_URL  = _cfg.get('barrier', 'server_url', fallback='http://127.0.0.1:3005/api/external/barrier')
OPEN_SECONDS        = float(_cfg.get('barrier', 'open_seconds', fallback='2.0'))
TAG_COOLDOWN   = float(_cfg.get('scanner', 'tag_cooldown', fallback='5.0'))
READER_HOST    = _cfg.get('scanner', 'reader_host', fallback='192.168.78.8')
READER_PORT    = int(_cfg.get('scanner', 'reader_port', fallback='9090'))

ENTRY_URL      = f"{API_BASE}/api/v1/tolls/entry/"
EXIT_URL       = f"{API_BASE}/api/v1/tolls/exit/"
FARE_DISPLAY   = f"http://{DISPLAY_IP}/?vehicle_number=Q.TAG&fare_amount={{fare}}"
THANKYOU_URL   = f"http://{DISPLAY_IP}/thankyou"
WELCOME_URL    = f"http://{DISPLAY_IP}/?vehicle_number=WELCOME&take_slip"
# ─────────────────────────────────────────────────────────────────────────────


def normalize_tid(tid: str) -> str:
    return tid.replace(" ", "").upper() if tid else ""


class ApiClient:
    """Calls /api/v1/tolls/entry/ or /api/v1/tolls/exit/ based on GATE_MODE."""

    _headers = {
        'Authorization': f'Bearer {OPERATOR_TOKEN}',
        'Content-Type': 'application/json',
    }

    @classmethod
    def process_tag(cls, tag_serial: str) -> dict:
        payload = {'tag_serial': tag_serial, 'plaza_id': PLAZA_ID}
        if LANE_ID:
            payload['lane_id'] = LANE_ID

        url = ENTRY_URL if GATE_MODE == 'entry' else EXIT_URL
        try:
            resp = requests.post(url, json=payload, headers=cls._headers, timeout=5)
            body = resp.json()
            if resp.status_code == 200 and body.get('success'):
                return body
            reason = body.get('message') or body.get('reason') or f'HTTP {resp.status_code}'
            return {'success': False, 'reason': reason}
        except requests.RequestException as exc:
            return {'success': False, 'reason': f'API unreachable: {exc}'}


class RfidGate(IAsynchronousMessage):
    def __init__(self):
        self.last_seen: dict = {}
        self.last_barrier_trigger: dict = {}
        print(f"[gate] Mode: {GATE_MODE.upper()} | Plaza: {PLAZA_ID} | Lane: {LANE_ID or 'unset'}")
        print(f"[barrier] Using server: {BARRIER_SERVER_URL}")

    # ── Barrier ──────────────────────────────────────────────────────────────

    def _open_barrier(self):
        """Barrier server ko HTTP POST karo — server khud serial handle karta hai aur auto-close bhi karta hai."""
        def _call():
            try:
                resp = requests.post(
                    BARRIER_SERVER_URL,
                    json={"action": "open", "source": "rfid"},
                    timeout=10
                )
                if resp.status_code == 200:
                    print("[barrier] Opened successfully via server")
                else:
                    print(f"[barrier] Server error: {resp.status_code} — {resp.text}")
            except Exception as exc:
                print(f"[barrier] HTTP call failed: {exc}")
        threading.Thread(target=_call, daemon=True).start()

    def _schedule_close(self):
        """OPEN_SECONDS baad UFD pe thank-you dikhao — barrier close server side hota hai."""
        def _thankyou():
            time.sleep(OPEN_SECONDS)
            try:
                requests.get(THANKYOU_URL, timeout=2)
            except Exception:
                pass
        threading.Thread(target=_thankyou, daemon=True).start()

    # ── Display ──────────────────────────────────────────────────────────────

    def _show_fare(self, fare):
        try:
            requests.get(FARE_DISPLAY.format(fare=fare), timeout=2)
        except Exception:
            pass

    def _show_denied(self):
        try:
            requests.get(f"http://{DISPLAY_IP}/?vehicle_number=Q.TAG&fare_amount=0", timeout=2)
        except Exception:
            pass

    # ── RFID Callbacks ────────────────────────────────────────────────────────

    def OutputTags(self, tag):
        try:
            tag_epc = getattr(tag, '_EPC', '') or ''
            tag_tid = normalize_tid(getattr(tag, '_TID', ''))
            now = datetime.now()

            if not tag_tid:
                print(f"[warn] Tag scanned but TID is empty (EPC={tag_epc or 'none'}) — check extended-read config")
                return

            # deduplicate within 1 second
            key = (tag_epc, tag_tid)
            if key in self.last_seen and (now - self.last_seen[key]).total_seconds() <= 1:
                return
            self.last_seen[key] = now

            print(f"\n>>> EPC: {tag_epc} | TID: {tag_tid} | {now} | mode={GATE_MODE.upper()}")

            # per-tag cooldown
            now_ts = time.time()
            if tag_tid in self.last_barrier_trigger:
                elapsed = now_ts - self.last_barrier_trigger[tag_tid]
                if elapsed < TAG_COOLDOWN:
                    print(f"[cooldown] {tag_tid} — wait {TAG_COOLDOWN - elapsed:.1f}s")
                    return
            self.last_barrier_trigger[tag_tid] = now_ts

            result = ApiClient.process_tag(tag_tid)

            if not result.get('success'):
                reason = result.get('reason', 'denied')
                print(f"[gate] DENIED — {reason}")
                self._show_denied()
                return

            # Django returns 'charge' at exit, 'current_balance' at entry
            fare = result.get('charge') or result.get('current_balance', '0')
            self._show_fare(fare)
            self._open_barrier()
            self._schedule_close()

            if GATE_MODE == 'exit':
                print(
                    f"[gate] EXIT OK — vehicle: {result.get('vehicle')} "
                    f"charge: Rs.{result.get('charge')} "
                    f"balance: Rs.{result.get('balance_remaining')}"
                )
            else:
                print(
                    f"[gate] ENTRY OK — vehicle: {result.get('vehicle')} "
                    f"balance: Rs.{result.get('current_balance')}"
                )

        except Exception as exc:
            print(f"[error] OutputTags: {exc}")

    def OutputTagsOver(self, connID):
        print(f"[reader] Connection {connID} finished")

    def WriteDebugMsg(self, connID, msg):
        pass

    def WriteLog(self, connID, msg):
        pass

    def PortConnecting(self, connID):
        print(f"[reader] Device connected: {connID}")

    def PortClosing(self, connID):
        print(f"[reader] Device disconnected: {connID}")

    def GPIControlMsg(self, connID, gpi_model):
        pass

    def OutputScanData(self, connID, scandata):
        pass

    # ── Entry Point ───────────────────────────────────────────────────────────

    @staticmethod
    def main():
        if not PLAZA_ID or PLAZA_ID == '00000000-0000-0000-0000-000000000000':
            print("[ERROR] plaza_id not set in rfid_config.ini — update it before starting.")
            return
        if not OPERATOR_TOKEN or OPERATOR_TOKEN == 'PASTE_OPERATOR_JWT_HERE':
            print("[ERROR] operator_token not set in rfid_config.ini — update it before starting.")
            return

        gate = RfidGate()
        tcp = f"TCP:{READER_HOST}:{READER_PORT}"
        RECONNECT_DELAY = 5
        MAX_CONSECUTIVE_FAILURES = 3

        try:
            requests.get(WELCOME_URL, timeout=2)
            print("[display] Welcome screen shown.")
        except Exception:
            pass

        from com.rfid.enumeration import EReaderResult
        try:
            while True:
                reader = Reader()
                if not reader.initReader(tcp, gate):
                    print(f"[reader] Cannot connect to {tcp} — retrying in {RECONNECT_DELAY}s")
                    time.sleep(RECONNECT_DELAY)
                    continue

                print(f"[reader] Connected to {tcp}")
                reader.paramSet(
                    EReaderEnum.WO_RFIDReadExtended,
                    [ReadExtendedArea_Model(EReadBank.TID, 0, 6, "")]
                )

                consecutive_failures = 0
                while True:
                    try:
                        requests.get(WELCOME_URL, timeout=2)
                    except Exception:
                        pass
                    print("[reader] Scanning...")
                    result = reader.inventory()
                    if result not in (EReaderResult.RT_OK, EReaderResult.RT_TIMEOUT_ERR):
                        consecutive_failures += 1
                        print(f"[reader] inventory error ({result}) — attempt {consecutive_failures}/{MAX_CONSECUTIVE_FAILURES}")
                        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                            print(f"[reader] Connection lost — reconnecting in {RECONNECT_DELAY}s")
                            time.sleep(RECONNECT_DELAY)
                            break
                    else:
                        consecutive_failures = 0
                    time.sleep(1)

        except KeyboardInterrupt:
            print("\n[gate] Interrupted")


if __name__ == '__main__':
    RfidGate.main()

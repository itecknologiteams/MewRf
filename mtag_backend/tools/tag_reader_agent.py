#!/usr/bin/env python3
"""Desktop USB RFID reader → M-Tag registration desk.

Runs on the operator's PC, not on a booth. The registration portal is served
over plain HTTP on a LAN address, and browsers expose navigator.serial only in a
secure context (HTTPS or localhost) — so the page cannot read the COM port
itself. This agent reads it instead.

    # 1. Confirm the reader is seen (the port is auto-detected, so this is
    #    only needed when something looks wrong)
    python tag_reader_agent.py --list

    # 2. See exactly what your reader sends when a tag is placed on it.
    #    Run this FIRST — the parser below is a guess until we know the format.
    python tag_reader_agent.py --raw

    # 3. Once the format is known, watch reads as they are parsed
    python tag_reader_agent.py

    # 4. Feed the portal (needs an operator login on this machine)
    python tag_reader_agent.py \\
        --api https://api.maliroperations.com/api/v1 \\
        --phone 03001234567 --password ...

The port is auto-detected: legacy /dev/ttyS* are ignored and a device whose
description mentions a reader wins. Override with --port (COM3 on Windows).

Windows needs no permission setup — HID and COM are open to the logged-in user.
On Linux the device nodes are root/dialout owned, so a first run needs the udev
rule in this bundle (install.sh does it) and:
    sudo usermod -aG dialout $USER    # then log out and back in
"""

import argparse
import binascii
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Windows consoles still default to a legacy codepage in places, where the
# em-dashes below raise UnicodeEncodeError in the middle of a read. Degrade the
# character rather than the run.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    sys.exit("pyserial is required:  pip install pyserial")

# A TID/EPC is hex. Most desktop readers in free-run mode emit one read per
# line, as E280..., "E2 80 11 ..." or "e2-80-11-...", sometimes behind a prefix.
# Separators are stripped after matching so all three normalise to what the
# database stores. If your reader frames its output in binary instead, --raw
# will show that and this needs replacing rather than tweaking.
HEX_RUN = re.compile(rb'([0-9A-Fa-f]{2}(?:[ \-]?[0-9A-Fa-f]{2}){7,31})')
MIN_HEX_CHARS = 16


def _normalise(raw: bytes) -> str:
    return raw.decode().replace(' ', '').replace('-', '').upper()


# Every PC enumerates legacy serial ports that are almost never the reader:
# dozens of /dev/ttyS* 8250 ports on Linux, and the motherboard's COM1
# ("Communications Port") on Windows. Listing them buries the one device that
# matters, so they are hidden unless --all is passed.
LEGACY_PORT = re.compile(r'/dev/ttyS\d+$')
READER_WORDS = ('reader', 'uhf', 'rfid', 'nfc')

# HopeLand desktop UHF reader. It enumerates as a composite device: a CDC serial
# port AND a HID interface. The serial port never speaks — the protocol runs
# over HID — so this is the connection the SDK is given by default.
HOPELAND_VID = 0x2121
HOPELAND_PID = 0x8633


def candidate_ports():
    """Ports that could plausibly be the reader, best guess first."""
    real = [
        p for p in list_ports.comports()
        # Require a USB vendor id. Windows' motherboard COM1 has an ACPI hwid but
        # no vid; testing hwid instead let it through as "the reader".
        if not LEGACY_PORT.match(p.device) and p.vid is not None
    ]

    def rank(port):
        text = f"{port.description or ''} {port.manufacturer or ''}".lower()
        return (0 if any(w in text for w in READER_WORDS) else 1, port.device)

    return sorted(real, key=rank)


def autodetect_port():
    found = candidate_ports()
    if not found:
        sys.exit(
            "No USB serial device found. Plug the reader in, or pass --port "
            "explicitly (--list --all shows every port including legacy ones)."
        )
    chosen = found[0]
    if len(found) > 1:
        others = ', '.join(p.device for p in found[1:])
        print(f"Note: more than one USB serial device; also saw {others}")
    print(f"Using {chosen.device} ({chosen.description or 'no description'})")
    return chosen.device


def list_serial_ports(show_all=False):
    ports = list(list_ports.comports()) if show_all else candidate_ports()
    if not ports:
        print("No serial ports found. Is the reader plugged in?")
        if not show_all:
            print("(legacy ports (/dev/ttyS*, motherboard COM) hidden — pass --all to see them)")
        return
    print(f"{'PORT':<22} {'DESCRIPTION':<40} HWID")
    for p in ports:
        print(f"{p.device:<22} {(p.description or '')[:40]:<40} {p.hwid or ''}")
    if not show_all:
        print("\n(legacy ports (/dev/ttyS*, motherboard COM) hidden — pass --all to see them)")


def raw_dump(port, baud):
    """Print everything the reader sends, as hex and as text.

    The point of this mode: nobody has told me your reader's frame format, and
    guessing it silently would mean a parser that looks like it works and drops
    reads. Place a tag on the reader a few times and send me what appears here.
    """
    print(f"Listening on {port} at {baud} baud. Place a tag on the reader.")
    print("Ctrl-C to stop.\n")
    with serial.Serial(port, baud, timeout=0.2) as conn:
        buffer = bytearray()
        last = time.monotonic()
        started = time.monotonic()
        total = 0
        hinted = False
        while True:
            chunk = conn.read(256)
            if chunk:
                buffer += chunk
                last = time.monotonic()
                total += len(chunk)
                continue

            # Silence is ambiguous: it can mean the reader free-runs and no tag
            # is present, OR that it waits for a start command and will never
            # speak on its own. Say so rather than letting it look like a hang.
            if not hinted and total == 0 and time.monotonic() - started > 12:
                hinted = True
                print("No data after 12s. Either no tag has been presented, or this")
                print("reader only reports after a start command — in which case we")
                print("need its protocol/command set (vendor doc or demo tool).")
                print(f"Try a different baud too: --baud 9600 / 57600 / 38400.\n")
            # A quiet gap means one frame has ended.
            if buffer and time.monotonic() - last > 0.25:
                printable = ''.join(
                    chr(b) if 32 <= b < 127 else '.' for b in buffer
                )
                print(f"  {len(buffer):>3} bytes")
                print(f"  hex   : {binascii.hexlify(buffer, ' ').decode()}")
                print(f"  ascii : {printable}")
                candidates = [_normalise(m) for m in HEX_RUN.findall(bytes(buffer))]
                if candidates:
                    print(f"  looks like a tag id: {', '.join(candidates)}")
                print()
                buffer.clear()


# ── Vendor SDK (the reliable path) ───────────────────────────────────────────
# This reader stays silent until it is told to run an inventory, so raw serial
# reading sees nothing. The SDK vendored at mtag_backend/vendor/rfid_sdk speaks
# the protocol and already drives the lane readers over TCP; the only difference
# here is the connection string. Mirrors run_gate.py's sequence deliberately —
# that one is known to read TID reliably on this hardware.

def _add_sdk_to_path():
    """Find com.rfid whether this runs from the repo or a standalone bundle."""
    here = os.path.dirname(os.path.abspath(__file__))
    for candidate in (
        os.path.join(os.path.dirname(here), 'vendor', 'rfid_sdk'),  # repo layout
        os.path.join(here, 'vendor', 'rfid_sdk'),                   # script beside vendor/
        os.path.join(here, 'rfid_sdk'),
        here,
    ):
        if os.path.isdir(os.path.join(candidate, 'com')) and candidate not in sys.path:
            sys.path.insert(0, candidate)
            return


def find_hid_reader():
    """The reader's USB id, in the 'ID vvvv:pppp' form UsbConnect parses."""
    _add_sdk_to_path()
    try:
        import hid
    except ImportError:
        print("Note: hidapi is not installed, so the reader's USB HID interface "
              "cannot be used.\n    python -m pip install hidapi")
        return None
    if not hasattr(hid, 'device'):
        sys.exit(
            "The installed 'hid' package is the wrong one: the SDK needs "
            "hid.device(), which comes from `hidapi`.\n"
            "    pip uninstall -y hid && pip install hidapi"
        )
    try:
        for info in hid.enumerate(HOPELAND_VID, HOPELAND_PID):
            return f"ID {HOPELAND_VID:04x}:{HOPELAND_PID:04x}"
    except Exception as exc:
        print(f"Note: could not enumerate USB HID devices ({exc}).")
        return None
    # Say so. Falling back silently meant the next line named some serial port as
    # "the reader", when the real finding was that the reader was not seen at all.
    print(
        f"Note: no HopeLand reader ({HOPELAND_VID:04x}:{HOPELAND_PID:04x}) found on "
        f"USB HID — falling back to a serial port, which this reader does not "
        f"answer on. Check the reader is plugged in and not held by another program."
    )
    return None


def sdk_watch(conn, portal, on_tag=None):
    _add_sdk_to_path()
    try:
        from com.rfid.Reader import Reader
        from com.rfid.enumeration import EReaderEnum, EReadBank, EReaderResult
        from com.rfid.models import ReadExtendedArea_Model
        from com.rfid.models.ReaderInfo_Model import ReaderInfo_Model
        from com.rfid.interface import IAsynchronousMessage
    except ImportError as exc:
        missing = getattr(exc, 'name', None) or ''
        if missing and not missing.startswith('com'):
            # The SDK folder WAS found — one of its own imports failed. Pointing at
            # the SDK path here sent people hunting for a folder that was present.
            package = {'usb': 'pyusb', 'hid': 'hidapi', 'serial': 'pyserial'}.get(
                missing.split('.')[0], missing)
            sys.exit(
                f"The com.rfid SDK needs the '{missing}' module, which is not installed.\n"
                f"    python -m pip install {package}\n"
                "(or re-run install.bat / install.sh from the reader bundle)"
            )
        sys.exit(
            f"Could not import the com.rfid SDK ({exc}).\n"
            "Expected it at mtag_backend/vendor/rfid_sdk/com — run this script "
            "from a checkout that has it, or add it to PYTHONPATH."
        )

    seen = {}

    class _Listener(IAsynchronousMessage):
        def OutputTags(self, tag):
            try:
                epc = (getattr(tag, '_EPC', '') or '').replace(' ', '').upper()
                tid = (getattr(tag, '_TID', '') or '').replace(' ', '').upper()
                key = tid or epc
                if not key:
                    return
                now = time.monotonic()
                # A reader in inventory mode reports the same tag many times a
                # second; the operator placed ONE tag, so report it once.
                if now - seen.get(key, 0) < 2.0:
                    return
                seen[key] = now
                _report(key, tid, epc, portal, on_tag)
            except Exception as exc:
                print(f"  [error] {exc}")

        def OutputTagsOver(self, conn_id): pass
        def WriteDebugMsg(self, conn_id, msg): pass
        def WriteLog(self, conn_id, msg): pass
        def PortConnecting(self, conn_id): print(f"Reader connected: {conn_id}")
        def PortClosing(self, conn_id): print(f"Reader disconnected: {conn_id}")
        def GPIControlMsg(self, conn_id, gpi): pass
        def OutputScanData(self, conn_id, data): pass

    reader = Reader()
    if not reader.initReader(conn, _Listener()):
        if conn.startswith('USB:') and sys.platform.startswith('win'):
            hint = (
                "\nIf this says 'open failed', another program is holding the "
                "reader.\nClose any HopeLand demo tool, then unplug and replug it."
            )
        else:
            hint = (
            "\nIf this says 'open failed', it is almost certainly permissions:\n"
            "/dev/hidraw* is root-only by default. Install the udev rule once:\n"
            "    sudo cp deploy/99-hopeland-uhf-reader.rules /etc/udev/rules.d/\n"
            "    sudo udevadm control --reload-rules && sudo udevadm trigger\n"
            "then unplug and replug the reader."
        ) if conn.startswith('USB:') else (
            "\nCheck the port and baud (--baud), and that nothing else holds it."
        )
        sys.exit(f"The SDK could not open {conn}.{hint}")
    print(f"Connected over {conn}")

    info = ReaderInfo_Model()
    if reader.paramGet(EReaderEnum.RO_ReaderInformation, info) == EReaderResult.RT_OK:
        print(f"Reader SN: {info.readerSN}")

    # Without this the reader uploads EPC only and _TID stays empty — and the
    # TID is what identifies the physical tag in inventory.
    tid_result = reader.paramSet(
        EReaderEnum.WO_RFIDReadExtended,
        [ReadExtendedArea_Model(EReadBank.TID, 0, 6, "")],
    )
    if tid_result == EReaderResult.RT_OK:
        print("Extended TID read enabled")
    else:
        print(f"WARNING: reader rejected extended TID read ({tid_result}) — "
              "reads will carry EPC only")

    print("\nPlace a tag on the reader. Ctrl-C to stop.\n")
    try:
        while True:
            result = reader.inventory()
            if result not in (EReaderResult.RT_OK, EReaderResult.RT_TIMEOUT_ERR):
                print(f"  inventory error: {result}")
            time.sleep(0.5)
    finally:
        try:
            reader.closeConnect()
        except Exception:
            pass


# ── Local publisher ──────────────────────────────────────────────────────────
# The reader is on the operator's PC; the backend is on master. Rather than give
# every registration PC a set of API credentials so the agent can talk to master
# directly, the agent publishes reads on loopback and the BROWSER — which is
# already logged in — does the lookup. Nothing here needs a secret, and a read
# never leaves the machine except as the operator's own authenticated request.


class _LastRead:
    """The most recent read, with a sequence number so the page can tell a new
    placement from a re-poll of the same one."""

    def __init__(self):
        self._lock = threading.Lock()
        self.seq = 0
        self.tid = ''
        self.epc = ''
        self.at = 0.0

    def set(self, tid, epc):
        with self._lock:
            self.seq += 1
            self.tid, self.epc, self.at = tid, epc, time.time()

    def payload(self):
        with self._lock:
            return {
                'seq': self.seq, 'tid': self.tid, 'epc': self.epc,
                'at': self.at, 'agent': 'mtag-tag-reader',
            }


def serve_reads(last, port):
    class Handler(BaseHTTPRequestHandler):
        def _cors(self):
            # The portal may be opened as localhost or as a LAN address. Chrome
            # treats the latter reaching loopback as a private-network request
            # and preflights it, which is what the third header answers.
            self.send_header('Access-Control-Allow-Origin', self.headers.get('Origin', '*'))
            self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
            self.send_header('Access-Control-Allow-Private-Network', 'true')
            self.send_header('Cache-Control', 'no-store')

        def do_OPTIONS(self):
            self.send_response(204)
            self._cors()
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.end_headers()

        def do_GET(self):
            if self.path.split('?')[0] not in ('/tag', '/'):
                self.send_response(404)
                self._cors()
                self.end_headers()
                return
            body = json.dumps(last.payload()).encode()
            self.send_response(200)
            self._cors()
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass  # one line per poll would drown the reader output

    try:
        server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    except OSError as exc:
        if getattr(exc, 'errno', None) in (48, 98) or 'in use' in str(exc).lower():
            sys.exit(
                f"Port {port} is already in use — another copy of this agent is "
                f"probably still running.\n"
                f"Close that window first, or start this one on another port:\n"
                f"    --serve {port + 1}   (then set VITE_READER_AGENT_URL to match)"
            )
        raise
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"Publishing reads on http://127.0.0.1:{port}/tag")
    return server


def _report(key, tid, epc, portal, on_tag=None):
    if on_tag is not None:
        on_tag(tid, epc)
        return
    if portal is None:
        print(f"TAG  tid={tid or '-'}  epc={epc or '-'}")
        return
    try:
        result = portal.lookup(key)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(f"TAG  {key}  — lookup failed: {exc}")
        return
    mark = 'OK  ' if result.get('available') else 'NO  '
    print(f"{mark}{key}  {result.get('message', '')}")


def parse_reads(chunk: bytes):
    """Best-effort tag ids out of one frame. Verify with --raw before trusting."""
    out = []
    for match in HEX_RUN.findall(chunk):
        value = _normalise(match)
        if len(value) >= MIN_HEX_CHARS:
            out.append(value)
    return out


class Portal:
    """Talks to the backend as an operator so a read can be identified."""

    def __init__(self, base, phone, password):
        self.base = base.rstrip('/')
        self.token = None
        if phone and password:
            self.token = self._login(phone, password)

    def _request(self, path, payload=None, method='GET'):
        data = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(
            f"{self.base}{path}", data=data, method=method,
            headers={'Content-Type': 'application/json'},
        )
        if self.token:
            request.add_header('Authorization', f'Bearer {self.token}')
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode() or '{}')

    def _login(self, phone, password):
        try:
            body = self._request(
                '/auth/login/', {'phone': phone, 'password': password}, 'POST')
        except (urllib.error.URLError, OSError, ValueError) as exc:
            sys.exit(f"Could not log in to {self.base}: {exc}")
        data = body.get('data') or {}
        token = data.get('access') or (data.get('tokens') or {}).get('access')
        if not token:
            sys.exit(
                "Login succeeded but no access token was returned. This build may "
                "use httpOnly cookies only — run without --phone/--password and "
                "use --raw / local mode instead."
            )
        print(f"Logged in to {self.base}")
        return token

    def lookup(self, tid):
        return (self._request(
            f'/vehicles/tags/scan-lookup/?tid={tid}&epc={tid}') or {}).get('data', {})


def watch(port, baud, portal):
    print(f"Reading {port} at {baud} baud. Ctrl-C to stop.\n")
    seen = {}
    with serial.Serial(port, baud, timeout=0.2) as conn:
        buffer = bytearray()
        last = time.monotonic()
        while True:
            chunk = conn.read(256)
            if chunk:
                buffer += chunk
                last = time.monotonic()
                continue
            if not buffer or time.monotonic() - last <= 0.25:
                continue

            for tid in parse_reads(bytes(buffer)):
                now = time.monotonic()
                # A reader left in free-run mode repeats the same tag many times
                # a second; report a tag once per placement, not per read.
                if now - seen.get(tid, 0) < 2.0:
                    continue
                seen[tid] = now
                if portal is None:
                    print(f"TAG {tid}")
                    continue
                try:
                    result = portal.lookup(tid)
                except (urllib.error.URLError, OSError, ValueError) as exc:
                    print(f"TAG {tid}  — lookup failed: {exc}")
                    continue
                mark = 'OK  ' if result.get('available') else 'NO  '
                print(f"{mark}{tid}  {result.get('message', '')}")
            buffer.clear()


def main():
    parser = argparse.ArgumentParser(
        description="Read a USB RFID desktop reader for the registration desk.",
    )
    parser.add_argument('--list', action='store_true', help="List serial ports and exit.")
    parser.add_argument('--all', action='store_true',
                        help="With --list, include legacy /dev/ttyS* ports.")
    parser.add_argument('--port', help="Serial port. Auto-detected when omitted.")
    parser.add_argument('--baud', type=int, default=115200, help="Baud rate (default 115200).")
    parser.add_argument('--raw', action='store_true',
                        help="Dump raw serial bytes (diagnostic only — this reader "
                             "stays silent until the SDK asks it to inventory).")
    parser.add_argument('--no-sdk', action='store_true',
                        help="Read the port directly instead of via the vendor SDK.")
    parser.add_argument('--serial', action='store_true',
                        help="Force the SDK onto the serial port instead of HID.")
    parser.add_argument('--serve', nargs='?', const=8765, type=int, default=None,
                        metavar='PORT',
                        help="Publish reads on http://127.0.0.1:PORT/tag for the "
                             "registration page to pick up (default 8765).")
    parser.add_argument('--api', default='', help="Portal API base, e.g. https://host/api/v1")
    parser.add_argument('--phone', default='', help="Operator phone for --api.")
    parser.add_argument('--password', default='', help="Operator password for --api.")
    args = parser.parse_args()

    if args.list:
        list_serial_ports(args.all)
        return

    # Resolve the HID reader first: on this hardware the serial port is silent,
    # so announcing a ttyACM before falling back to HID just misleads.
    usb = None
    if not args.raw and not args.no_sdk and not args.serial:
        usb = find_hid_reader()
    port = args.port or ('' if usb else autodetect_port())
    try:
        portal = Portal(args.api, args.phone, args.password) if args.api else None

        on_tag = None
        if args.serve:
            last = _LastRead()
            serve_reads(last, args.serve)

            def on_tag(tid, epc, _last=last):
                _last.set(tid, epc)
                print(f"TAG  tid={tid or '-'}  epc={epc or '-'}  (published)")

        if args.raw:
            raw_dump(port, args.baud)
        elif args.no_sdk:
            watch(port, args.baud, portal)
        else:
            # HID first: on this reader the serial port is silent and only the
            # HID interface carries the protocol.
            sdk_watch(f"USB:{usb}" if usb else f"Serial:{port}:{args.baud}",
                      portal, on_tag=on_tag)
    except serial.SerialException as exc:
        if 'Permission denied' in str(exc) or 'Access is denied' in str(exc):
            if sys.platform.startswith('win'):
                sys.exit(
                    f"Access denied on {port}.\n"
                    "Another program is probably holding the port — close any "
                    "vendor demo tool or terminal using it, then retry."
                )
            sys.exit(
                f"Permission denied on {port}.\n"
                f"Serial devices belong to the 'dialout' group. Add yourself once:\n"
                f"    sudo usermod -aG dialout $USER\n"
                f"then log out and back in (or run: newgrp dialout)."
            )
        sys.exit(f"Could not open {port}: {exc}")
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == '__main__':
    main()

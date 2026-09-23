"""Reading a booth's own configuration and hardware, for the console at /booth/.

Everything here runs ON the booth, inside the mtag-web process, and answers the
questions an engineer standing at the lane has: what is this booth configured as,
can it see its reader, its barrier, its display and master, and what does the LPR
camera have to say.

Two things shape the whole module.

**Probes must be fast and must never raise.** They are called together to build
one overview payload behind a single HTTP request, so a reader that has been
unplugged has to answer "down" in two seconds rather than hanging the page. Every
probe therefore has its own short timeout and returns a dict — never an
exception — and "unknown" is a legitimate answer.

**Config edits must preserve the file.** rfid_config.ini is more comment than
setting, and those comments are the only documentation of what rssi_hysteresis
is for or why statement_timeout_ms is 10s. configparser round-trips would delete
every one of them, so writes here rewrite individual VALUE tokens in place and
leave the rest of the file byte-for-byte — the same approach set_rssi.sh takes
over SSH, which this is the in-browser equivalent of.
"""

import configparser
import json
import logging
import os
import re
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

CONFIG_FILENAME = 'rfid_config.ini'
BACKUP_SUFFIX = '.bak'

# Probe ceilings. The overview runs all of these; their sum is the worst case a
# user waits, so they are deliberately mean.
TCP_TIMEOUT = 2.0
HTTP_TIMEOUT = 2.0
DB_TIMEOUT = 3.0
PM2_TIMEOUT = 5.0
# Opening an RTSP stream, negotiating and decoding one keyframe is seconds of
# work even when the camera is healthy, so the camera is never part of the
# overview — it has its own endpoint and its own, longer, ceiling.
CAMERA_TIMEOUT = 15.0

BARRIER_STATUS_PATH = '/api/external/status'
BARRIER_CONTROL_PATH = '/api/external/barrier'


def base_dir() -> str:
    """The directory holding manage.py — where the gate's config and db live."""
    return os.path.dirname(
        os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', '..', 'manage.py')
        )
    )


def config_path() -> str:
    return os.path.join(base_dir(), CONFIG_FILENAME)


def is_booth() -> bool:
    """Whether this host is a booth at all.

    Master runs the same code from the same repository, so /booth/ exists there
    too. A missing rfid_config.ini is what distinguishes them, and the console
    says so rather than rendering a lane's worth of empty panels.
    """
    return os.path.exists(config_path())


# ── Reading the config ───────────────────────────────────────────────────────

# Keys whose values never leave the booth in an API response. rfid_config.ini
# carries no secret today, but it used to hold an [api] operator_token and a
# camera URL routinely carries a password in its userinfo.
_SECRET_KEY_RE = re.compile(r'token|password|secret|passwd|_key$', re.I)
_URL_USERINFO_RE = re.compile(r'(?P<scheme>[a-z][a-z0-9+.\-]*://)(?P<user>[^/:@\s]+):(?P<pw>[^/@\s]+)@')

REDACTED = '********'


def redact_url(value: str) -> str:
    """Strip the password out of a URL's userinfo, keeping the rest readable.

    rtsp://admin:hunter2@10.0.0.8/Streaming -> rtsp://admin:********@10.0.0.8/Streaming

    The username stays: it is half of what someone checking a camera's
    credentials needs, and on its own it unlocks nothing.
    """
    if not value:
        return value
    return _URL_USERINFO_RE.sub(
        lambda m: f"{m.group('scheme')}{m.group('user')}:{REDACTED}@", value)


def redact_value(key: str, value: str) -> str:
    if _SECRET_KEY_RE.search(key or ''):
        return REDACTED if value else ''
    return redact_url(value)


def read_config(path=None) -> dict:
    """Parse rfid_config.ini into sections, redacted, plus the raw text.

    The raw text is returned too — also redacted — because the comments are
    worth reading and the console shows them verbatim.
    """
    path = path or config_path()
    result = {
        'path': path,
        'exists': os.path.exists(path),
        'sections': {},
        'raw': '',
        'error': '',
        'modified_at': None,
        'backup_exists': os.path.exists(path + BACKUP_SUFFIX),
    }
    if not result['exists']:
        result['error'] = f"{CONFIG_FILENAME} not found — this host is not a booth."
        return result

    try:
        result['modified_at'] = os.path.getmtime(path)
        with open(path, encoding='utf-8') as handle:
            raw = handle.read()
    except OSError as exc:
        result['error'] = f"Cannot read {path}: {exc}"
        return result

    parser = configparser.ConfigParser()
    try:
        parser.read_string(raw)
    except configparser.Error as exc:
        # A malformed ini is exactly the fault that leaves a lane crash-looping,
        # so report it rather than returning an empty config that looks healthy.
        result['error'] = f"{CONFIG_FILENAME} is malformed: {exc}"
        result['raw'] = _redact_raw(raw)
        return result

    result['sections'] = {
        section: {key: redact_value(key, value) for key, value in parser[section].items()}
        for section in parser.sections()
    }
    result['raw'] = _redact_raw(raw)
    return result


def _redact_raw(raw: str) -> str:
    out = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped[0] in '#;[':
            out.append(line)
            continue
        if '=' not in line:
            out.append(line)
            continue
        key, _, value = line.partition('=')
        out.append(f"{key}={' ' if value.startswith(' ') else ''}{redact_value(key.strip(), value.strip())}")
    return '\n'.join(out)


def raw_config_parser(path=None) -> configparser.ConfigParser:
    """The unredacted config, for internal use (probing, camera URLs)."""
    parser = configparser.ConfigParser()
    parser.read(path or config_path())
    return parser


def _get(parser, section, key, fallback=''):
    try:
        return parser.get(section, key, fallback=fallback).strip()
    except (configparser.Error, AttributeError):
        return fallback


def gate_identity(parser=None) -> dict:
    """Who this booth thinks it is. Read straight from the file, not the DB."""
    parser = parser or raw_config_parser()
    legacy_min = _get(parser, 'scanner', 'rssi_filter', '0')
    legacy_max = _get(parser, 'scanner', 'rssi_filter_max', '0')
    return {
        'mode': _get(parser, 'gate', 'mode', 'entry').lower(),
        'plaza_id': _get(parser, 'gate', 'plaza_id'),
        'lane_number': _get(parser, 'gate', 'lane_number'),
        'lane_id': _get(parser, 'gate', 'lane_id'),
        'statement_timeout_ms': _get(parser, 'gate', 'statement_timeout_ms', '10000'),
        'reader_host': _get(parser, 'scanner', 'reader_host'),
        'reader_port': _get(parser, 'scanner', 'reader_port', '9090'),
        'antenna_power': _get(parser, 'scanner', 'antenna_power', '33'),
        'scan_interval': _get(parser, 'scanner', 'scan_interval', '1.0'),
        'tag_cooldown': _get(parser, 'scanner', 'tag_cooldown', '5.0'),
        # run_gate resolves the new three-threshold keys with the old
        # single-band ones as their fallback; mirror that exactly, or a booth
        # still on rssi_filter shows thresholds of 0 here while the gate is
        # actually filtering on them.
        'rssi_detect': _get(parser, 'scanner', 'rssi_detect', legacy_min),
        'rssi_open_min': _get(parser, 'scanner', 'rssi_open_min', legacy_min),
        'rssi_open_max': _get(parser, 'scanner', 'rssi_open_max', legacy_max),
        'rssi_window': _get(parser, 'scanner', 'rssi_window', '5'),
        'rssi_hysteresis': _get(parser, 'scanner', 'rssi_hysteresis', '3.0'),
        'barrier_port': _get(parser, 'barrier', 'port', '/dev/ttyUSB0'),
        'barrier_baudrate': _get(parser, 'barrier', 'baudrate', '115200'),
        'barrier_open_seconds': _get(parser, 'barrier', 'open_seconds', '2.0'),
        'barrier_mode': _get(parser, 'barrier', 'mode', 'auto').lower(),
        'barrier_service_url': _get(parser, 'barrier', 'service_url', 'http://127.0.0.1:3005'),
        'display_ip': _get(parser, 'display', 'display_ip'),
        'camera_rtsp_url': _get(parser, 'camera', 'rtsp_url'),
        'camera_transport': _get(parser, 'camera', 'transport', 'tcp'),
        'camera_snapshot_url': _get(parser, 'camera', 'snapshot_url'),
    }


# ── Writing the config ───────────────────────────────────────────────────────

# Only these may be changed from a browser. [gate] is deliberately absent: plaza
# number, lane number and entry/exit mode decide which plaza a vehicle is billed
# against, and re-pointing a live lane is a deployment decision made over SSH
# with someone watching, not a text box on a diagnostics page.
EDITABLE = {
    'scanner': {
        'reader_host', 'reader_port', 'tag_cooldown', 'antenna_power',
        'scan_interval', 'rssi_detect', 'rssi_open_min', 'rssi_open_max',
        'rssi_window', 'rssi_hysteresis',
    },
    'barrier': {'port', 'baudrate', 'open_seconds', 'mode',
                'service_url', 'service_cycle_seconds'},
    'display': {'display_ip'},
    'camera': {'rtsp_url', 'transport', 'snapshot_url'},
}

_HOST_RE = re.compile(r'^[A-Za-z0-9](?:[A-Za-z0-9.\-]{0,253}[A-Za-z0-9])?$')
_DEVICE_RE = re.compile(r'^(/dev/[A-Za-z0-9_./\-]+|COM\d+)$')
_BAUDRATES = {9600, 19200, 38400, 57600, 115200, 230400}


def _as_float(name, value, errors, low=None, high=None):
    try:
        number = float(value)
    except (TypeError, ValueError):
        errors.append(f"{name} must be a number, got '{value}'.")
        return None
    if low is not None and number < low:
        errors.append(f"{name} must be at least {low:g}, got {number:g}.")
    if high is not None and number > high:
        errors.append(f"{name} must be at most {high:g}, got {number:g}.")
    return number


def _as_int(name, value, errors, low=None, high=None):
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        errors.append(f"{name} must be a whole number, got '{value}'.")
        return None
    if low is not None and number < low:
        errors.append(f"{name} must be at least {low}, got {number}.")
    if high is not None and number > high:
        errors.append(f"{name} must be at most {high}, got {number}.")
    return number


def validate_changes(changes: dict, current: dict) -> list:
    """Reject anything run_gate would refuse to start on, before it is written.

    This is the whole point of putting the edit behind an API rather than a text
    editor. run_gate raises CommandError on a bad RSSI ordering, PM2 restarts it,
    and it raises again — a crash loop with the barrier down and the lane dead.
    The checks below are run_gate's own, applied to the merged result so that
    changing one threshold is validated against the two it is not changing.

    Returns a list of human-readable errors; empty means it is safe to write.
    """
    errors = []

    merged = dict(current)
    for (section, key), value in changes.items():
        if section not in EDITABLE or key not in EDITABLE[section]:
            errors.append(f"[{section}] {key} cannot be changed from the console.")
            continue
        merged[f'{section}.{key}'] = value
    if errors:
        return errors

    def value_of(section, key, default=''):
        return str(merged.get(f'{section}.{key}', default)).strip()

    # ── [scanner] ────────────────────────────────────────────────────────────
    host = value_of('scanner', 'reader_host')
    if host and not _HOST_RE.match(host):
        errors.append(f"reader_host '{host}' is not a valid hostname or IP.")
    _as_int('reader_port', value_of('scanner', 'reader_port', '9090'), errors, 1, 65535)
    _as_float('tag_cooldown', value_of('scanner', 'tag_cooldown', '5.0'), errors, 0.0, 300.0)
    _as_float('scan_interval', value_of('scanner', 'scan_interval', '1.0'), errors, 0.05, 60.0)
    # 33 dBm is the ceiling this reader family accepts; a higher value is
    # rejected by the reader, not clamped, so catch it here where it can be
    # explained.
    _as_int('antenna_power', value_of('scanner', 'antenna_power', '33'), errors, 0, 33)

    # Bounds-checked for their side effect on `errors`; run_gate refuses a
    # window below 1 and a negative hysteresis outright.
    _as_int('rssi_window', value_of('scanner', 'rssi_window', '5'), errors, 1)
    _as_float('rssi_hysteresis', value_of('scanner', 'rssi_hysteresis', '3.0'), errors, 0.0)
    detect = _as_float('rssi_detect', value_of('scanner', 'rssi_detect', '0'), errors)
    open_min = _as_float('rssi_open_min', value_of('scanner', 'rssi_open_min', '0'), errors)
    open_max = _as_float('rssi_open_max', value_of('scanner', 'rssi_open_max', '0'), errors)

    # These two mirror run_gate.Command.handle exactly. Keep them in step.
    if open_min and open_max and open_min > open_max:
        errors.append(
            f"rssi_open_min ({open_min:g}) is above rssi_open_max ({open_max:g}) "
            f"— the barrier could never open."
        )
    if detect and open_min and detect > open_min:
        errors.append(
            f"rssi_detect ({detect:g}) is above rssi_open_min ({open_min:g}) — a "
            f"vehicle would reach the barrier band before the gate ever noticed "
            f"it. Detect must be the weaker (more negative) threshold."
        )
    # ── [barrier] ────────────────────────────────────────────────────────────
    port = value_of('barrier', 'port', '/dev/ttyUSB0')
    if port and not _DEVICE_RE.match(port):
        errors.append(f"barrier port '{port}' is not a device path (/dev/... or COMn).")
    baud = _as_int('baudrate', value_of('barrier', 'baudrate', '115200'), errors, 300)
    if baud is not None and baud not in _BAUDRATES:
        errors.append(
            f"baudrate {baud} is not one of {sorted(_BAUDRATES)} — the relay will "
            f"not answer at that rate."
        )
    _as_float('open_seconds', value_of('barrier', 'open_seconds', '2.0'), errors, 0.1, 60.0)
    _as_float('service_cycle_seconds',
              value_of('barrier', 'service_cycle_seconds', '0.5'), errors, 0.0, 60.0)
    mode = value_of('barrier', 'mode', 'auto').lower()
    if mode and mode not in ('auto', 'serial'):
        errors.append(f"barrier mode must be 'auto' or 'serial', got '{mode}'.")
    service_url = value_of('barrier', 'service_url')
    if service_url and not service_url.startswith(('http://', 'https://')):
        errors.append(f"barrier service_url must be http(s)://, got '{service_url}'.")

    # ── [display] ────────────────────────────────────────────────────────────
    display_ip = value_of('display', 'display_ip')
    if display_ip and not _HOST_RE.match(display_ip):
        errors.append(f"display_ip '{display_ip}' is not a valid hostname or IP.")

    # ── [camera] ─────────────────────────────────────────────────────────────
    rtsp = value_of('camera', 'rtsp_url')
    if rtsp and not rtsp.startswith(('rtsp://', 'rtsps://', 'http://', 'https://')):
        errors.append(
            f"camera rtsp_url must start with rtsp:// (or http:// for an MJPEG "
            f"stream), got '{rtsp}'."
        )
    snapshot = value_of('camera', 'snapshot_url')
    if snapshot and not snapshot.startswith(('http://', 'https://')):
        errors.append(f"camera snapshot_url must be http(s)://, got '{snapshot}'.")
    transport = value_of('camera', 'transport', 'tcp').lower()
    if transport and transport not in ('tcp', 'udp'):
        errors.append(f"camera transport must be 'tcp' or 'udp', got '{transport}'.")

    return errors


def current_values(parser=None) -> dict:
    """Every editable key's present value, flattened to 'section.key'."""
    parser = parser or raw_config_parser()
    values = {}
    for section, keys in EDITABLE.items():
        for key in keys:
            values[f'{section}.{key}'] = _get(parser, section, key)
    return values


def write_changes(changes: dict, path=None) -> dict:
    """Rewrite the named values in place, keeping every comment and blank line.

    A key that exists in its section has its value token replaced. A key that
    does not is appended at the end of that section — which is why a new
    [camera] block can be created from the console without anyone editing the
    file by hand. A .bak of the previous file is left beside it, exactly as
    set_rssi.sh does, so a bad change is one `cp` away from undone.
    """
    path = path or config_path()
    with open(path, encoding='utf-8') as handle:
        lines = handle.read().splitlines()

    pending = {(s, k): str(v).strip() for (s, k), v in changes.items()}
    applied = {}

    # Where each section starts, and the last line in it that is not trailing
    # blank space — the insertion point for a key the section does not have.
    section_of_line = []
    current = ''
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('[') and stripped.endswith(']'):
            current = stripped[1:-1].strip().lower()
        section_of_line.append(current)

    # Pass 1 — replace values that already have a line.
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped[0] in '#;[' or '=' not in line:
            continue
        key_text, sep, value_text = line.partition('=')
        key = key_text.strip().lower()
        section = section_of_line[index]
        target = (section, key)
        if target not in pending:
            continue
        new_value = pending.pop(target)
        # Keep the original indentation and the spacing around '=' so the file
        # keeps looking like it was written by a person.
        leading = key_text[:len(key_text) - len(key_text.lstrip())]
        spacer = ' ' if value_text.startswith(' ') else ''
        lines[index] = f"{leading}{key_text.strip()} {sep}{spacer}{new_value}"
        applied[f'{section}.{key}'] = new_value

    # Pass 2 — append what is left, creating sections as needed.
    for (section, key), value in list(pending.items()):
        insert_at = None
        for index in range(len(lines) - 1, -1, -1):
            if section_of_line[index] == section and lines[index].strip():
                insert_at = index + 1
                break
        if insert_at is None:
            # `lines` and `section_of_line` are index-for-index parallel, and
            # the next key's insertion point comes from scanning the latter.
            # Appending a different number of entries to each left them out of
            # step whenever the file already ended in a blank line. That did not
            # actually misplace anything — the scan happens to land on the same
            # row either way — but it made a silent correctness argument out of a
            # coincidence, so extend them together and keep the invariant true.
            block = []
            if lines and lines[-1].strip():
                block.append('')
            block.append(f'[{section}]')
            block.append(f'{key} = {value}')
            lines.extend(block)
            section_of_line.extend([''] * (len(block) - 2) + [section, section])
        else:
            lines.insert(insert_at, f'{key} = {value}')
            section_of_line.insert(insert_at, section)
        applied[f'{section}.{key}'] = value

    body = '\n'.join(lines)
    if not body.endswith('\n'):
        body += '\n'

    # Verify the result parses BEFORE it replaces the live file. The gate reads
    # this on every start; a file that configparser chokes on is a dead lane.
    check = configparser.ConfigParser()
    check.read_string(body)

    shutil.copy2(path, path + BACKUP_SUFFIX)
    # Write-then-rename, so a process reading the file never sees a half-written
    # one and a full disk fails before the original is touched.
    temp_path = f"{path}.tmp.{os.getpid()}"
    try:
        with open(temp_path, 'w', encoding='utf-8') as handle:
            handle.write(body)
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    return {'applied': applied, 'backup': path + BACKUP_SUFFIX}


def restore_backup(path=None) -> bool:
    """Put back the .bak set aside by the last write."""
    path = path or config_path()
    backup = path + BACKUP_SUFFIX
    if not os.path.exists(backup):
        return False
    shutil.copy2(backup, path)
    return True


# ── Probes ───────────────────────────────────────────────────────────────────

def probe_tcp(host: str, port, timeout=TCP_TIMEOUT) -> dict:
    """Can this booth open a socket to the RFID reader?

    A connect is all that is attempted. Speaking the SDK's protocol would mean a
    second client on a reader that run_gate is already holding — and the SDK
    registry refuses a duplicate endpoint outright (see run_gate.run), so a
    probe that tried would report a failure caused by the probe itself.
    """
    result = {'target': f'{host}:{port}', 'ok': False, 'latency_ms': None, 'error': ''}
    if not host:
        result['error'] = 'not configured'
        return result
    try:
        port = int(port)
    except (TypeError, ValueError):
        result['error'] = f'invalid port {port!r}'
        return result

    started = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            result['ok'] = True
    except OSError as exc:
        result['error'] = str(exc)
    result['latency_ms'] = round((time.monotonic() - started) * 1000, 1)
    return result


def probe_http(url: str, timeout=HTTP_TIMEOUT, expect_json=False) -> dict:
    """GET a URL and report what came back.

    Any HTTP status counts as reachable: the UFD and the barrier service are
    embedded devices that answer 404 to a bare GET, and "it answered" is the
    fact being established, not "it liked the request".
    """
    result = {'target': url, 'ok': False, 'status': None,
              'latency_ms': None, 'error': '', 'body': None}
    if not url:
        result['error'] = 'not configured'
        return result

    started = time.monotonic()
    try:
        request = urllib.request.Request(url, headers={'Accept': '*/*'})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result['ok'] = True
            result['status'] = response.status
            if expect_json:
                raw = response.read(65536).decode('utf-8', 'replace')
                try:
                    result['body'] = json.loads(raw or '{}')
                except ValueError:
                    result['body'] = None
    except urllib.error.HTTPError as exc:
        result['ok'] = True
        result['status'] = exc.code
    except (urllib.error.URLError, OSError, ValueError) as exc:
        result['error'] = str(getattr(exc, 'reason', exc))
    result['latency_ms'] = round((time.monotonic() - started) * 1000, 1)
    return result


def probe_barrier_service(service_url: str) -> dict:
    """Is the qtserver barrier service up, and does it still hold its port?

    Mirrors BarrierBackend._probe's judgement: a service whose own serial port
    is shut cannot raise anything, so it is reported as down even though it
    answered.
    """
    service_url = (service_url or 'http://127.0.0.1:3005').rstrip('/')
    probe = probe_http(service_url + BARRIER_STATUS_PATH, expect_json=True)
    body = probe.get('body') or {}
    status = body.get('status') or {}
    probe['service_url'] = service_url
    probe['serial_open'] = status.get('isOpen')
    probe['usable'] = bool(probe['ok'] and body.get('success')
                           and status.get('isOpen', True))
    probe['detail'] = status
    return probe


def probe_serial(port: str) -> dict:
    """Does the relay's tty exist, and can this process write to it?

    Presence is not the same as ownership: when the barrier service is running
    it holds the port and the gate never touches it. Both facts are reported so
    the console can say which of the two is actually driving the boom.
    """
    result = {'target': port, 'exists': False, 'writable': False, 'error': ''}
    if not port:
        result['error'] = 'not configured'
        return result
    try:
        result['exists'] = os.path.exists(port)
        if result['exists']:
            result['writable'] = os.access(port, os.W_OK)
        else:
            result['error'] = 'device not present'
    except OSError as exc:
        result['error'] = str(exc)
    return result


def probe_database() -> dict:
    """Round-trip one query to master, and say which host answered.

    Booths are online-only — master IS the database — so this is the single
    probe that decides whether the lane can charge anybody at all.
    """
    from django.conf import settings
    from django.db import connection

    config = settings.DATABASES.get('default', {})
    result = {
        'host': config.get('HOST', ''),
        'name': config.get('NAME', ''),
        'ok': False,
        'latency_ms': None,
        'error': '',
    }
    started = time.monotonic()
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        result['ok'] = True
    except Exception as exc:
        result['error'] = str(exc).strip().splitlines()[0] if str(exc) else repr(exc)
    result['latency_ms'] = round((time.monotonic() - started) * 1000, 1)
    return result


# ── PM2 ──────────────────────────────────────────────────────────────────────

def _pm2_binary():
    found = shutil.which('pm2')
    if found:
        return found
    # PM2 is installed per-user via npm and gunicorn's PATH under systemd is
    # often just /usr/bin:/bin, so `which` misses it on exactly the booths where
    # it matters. Check where booth_bootstrap.sh puts it.
    candidates = [
        '/usr/local/bin/pm2', '/usr/bin/pm2',
        os.path.expanduser('~/.npm-global/bin/pm2'),
        os.path.expanduser('~/.nvm/versions/node/current/bin/pm2'),
    ]
    for candidate in candidates:
        if os.path.exists(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return ''


def pm2_status() -> dict:
    """What PM2 says about mtag-gate and mtag-web on this booth."""
    result = {'available': False, 'processes': [], 'error': ''}
    binary = _pm2_binary()
    if not binary:
        result['error'] = 'pm2 not found on PATH'
        return result
    try:
        completed = subprocess.run(
            [binary, 'jlist'], capture_output=True, text=True, timeout=PM2_TIMEOUT,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        result['error'] = str(exc)
        return result
    if completed.returncode != 0:
        result['error'] = (completed.stderr or completed.stdout or '').strip()[:400]
        return result
    try:
        entries = json.loads(completed.stdout or '[]')
    except ValueError as exc:
        result['error'] = f'unreadable pm2 jlist output: {exc}'
        return result

    result['available'] = True
    for entry in entries:
        env = entry.get('pm2_env') or {}
        monit = entry.get('monit') or {}
        uptime_ms = env.get('pm_uptime')
        result['processes'].append({
            'name': entry.get('name', ''),
            'status': env.get('status', ''),
            'pid': entry.get('pid'),
            'restarts': env.get('restart_time', 0),
            'unstable_restarts': env.get('unstable_restarts', 0),
            'uptime_seconds': (
                round(time.time() - uptime_ms / 1000.0) if uptime_ms else None),
            'cpu': monit.get('cpu'),
            'memory_mb': (
                round(monit.get('memory', 0) / 1048576.0, 1)
                if monit.get('memory') else None),
        })
    return result


def pm2_restart(process='mtag-gate') -> dict:
    """Restart one PM2 app. Only the two this project owns may be named."""
    if process not in ('mtag-gate', 'mtag-web'):
        return {'ok': False, 'error': f'refusing to restart {process!r}'}
    binary = _pm2_binary()
    if not binary:
        return {'ok': False, 'error': 'pm2 not found on PATH'}
    try:
        completed = subprocess.run(
            [binary, 'restart', process, '--update-env'],
            capture_output=True, text=True, timeout=60,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        return {'ok': False, 'error': str(exc)}
    output = ((completed.stdout or '') + (completed.stderr or '')).strip()[:2000]
    return {'ok': completed.returncode == 0, 'output': output,
            'exit_code': completed.returncode}


def pm2_log_tail(process='mtag-gate', lines=200) -> dict:
    """The tail of a PM2 app's stdout log, read straight off disk.

    `pm2 logs` streams and never returns, so the file is read directly. Both the
    default log location and PM2_HOME are checked because a booth provisioned
    under a service account puts them somewhere other than ~/.pm2.
    """
    if process not in ('mtag-gate', 'mtag-web'):
        return {'ok': False, 'error': f'refusing to read logs for {process!r}', 'lines': []}
    lines = max(10, min(int(lines or 200), 2000))
    home = os.environ.get('PM2_HOME') or os.path.join(os.path.expanduser('~'), '.pm2')
    candidates = [
        os.path.join(home, 'logs', f'{process}-out.log'),
        os.path.join(home, 'logs', f'{process}-out-0.log'),
        os.path.join(home, 'logs', f'{process}-error.log'),
    ]
    for candidate in candidates:
        if not os.path.exists(candidate):
            continue
        try:
            with open(candidate, 'rb') as handle:
                # Seek back a generous slice rather than reading a log that may
                # be hundreds of megabytes.
                handle.seek(0, os.SEEK_END)
                size = handle.tell()
                span = min(size, lines * 400)
                handle.seek(size - span)
                text = handle.read().decode('utf-8', 'replace')
            tail = text.splitlines()
            if span < size and tail:
                tail = tail[1:]  # first line is probably cut mid-way
            return {'ok': True, 'path': candidate, 'lines': tail[-lines:]}
        except OSError as exc:
            return {'ok': False, 'error': str(exc), 'path': candidate, 'lines': []}
    return {'ok': False, 'error': f'no log file found under {home}/logs', 'lines': []}


# ── LPR camera ───────────────────────────────────────────────────────────────

def _ffmpeg_binary(name='ffmpeg'):
    found = shutil.which(name)
    if found:
        return found
    for candidate in (f'/usr/bin/{name}', f'/usr/local/bin/{name}', f'/snap/bin/{name}'):
        if os.path.exists(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return ''


def camera_available() -> dict:
    return {
        'ffmpeg': bool(_ffmpeg_binary('ffmpeg')),
        'ffprobe': bool(_ffmpeg_binary('ffprobe')),
    }


def camera_snapshot(rtsp_url: str, transport='tcp', timeout=CAMERA_TIMEOUT):
    """One JPEG frame off the LPR stream, or an explanation.

    RTSP cannot be played by a browser, so the stream is decoded here and the
    page shows stills. This is a diagnostic view — "is the camera up, aimed at
    the lane, and in focus" — not a video wall, and a still answers all three.

    The URL is passed as an argv element to a process started WITHOUT a shell,
    so its contents cannot become a command however they are punctuated.
    """
    binary = _ffmpeg_binary('ffmpeg')
    if not binary:
        return None, 'ffmpeg is not installed on this booth'
    if not rtsp_url:
        return None, 'no camera configured — set [camera] rtsp_url'

    command = [binary, '-nostdin', '-loglevel', 'error']
    if rtsp_url.startswith(('rtsp://', 'rtsps://')):
        command += ['-rtsp_transport', 'udp' if transport == 'udp' else 'tcp']
    command += [
        '-i', rtsp_url,
        '-frames:v', '1',
        '-q:v', '5',
        '-f', 'image2',
        '-vcodec', 'mjpeg',
        '-',
    ]
    try:
        completed = subprocess.run(
            command, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, (
            f'camera did not deliver a frame within {timeout:g}s — check the URL, '
            f'the credentials, and whether the stream is reachable from this booth'
        )
    except (subprocess.SubprocessError, OSError) as exc:
        return None, str(exc)

    if completed.returncode != 0 or not completed.stdout:
        detail = (completed.stderr or b'').decode('utf-8', 'replace').strip()
        return None, redact_url(detail[:500]) or 'ffmpeg produced no frame'
    return completed.stdout, ''


def camera_probe(rtsp_url: str, transport='tcp', timeout=CAMERA_TIMEOUT) -> dict:
    """What the stream says it is: codec, resolution, frame rate, bitrate."""
    result = {'ok': False, 'error': '', 'streams': [], 'format': {}}
    binary = _ffmpeg_binary('ffprobe')
    if not binary:
        result['error'] = 'ffprobe is not installed on this booth'
        return result
    if not rtsp_url:
        result['error'] = 'no camera configured — set [camera] rtsp_url'
        return result

    command = [binary, '-v', 'quiet', '-print_format', 'json',
               '-show_streams', '-show_format']
    if rtsp_url.startswith(('rtsp://', 'rtsps://')):
        command += ['-rtsp_transport', 'udp' if transport == 'udp' else 'tcp']
    command += ['-i', rtsp_url]

    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        result['error'] = f'no answer from the camera within {timeout:g}s'
        return result
    except (subprocess.SubprocessError, OSError) as exc:
        result['error'] = str(exc)
        return result

    if completed.returncode != 0:
        result['error'] = redact_url((completed.stderr or '').strip()[:500]) or \
            'ffprobe could not open the stream'
        return result

    try:
        payload = json.loads(completed.stdout or '{}')
    except ValueError as exc:
        result['error'] = f'unreadable ffprobe output: {exc}'
        return result

    result['ok'] = True
    for stream in payload.get('streams', []):
        result['streams'].append({
            'index': stream.get('index'),
            'type': stream.get('codec_type'),
            'codec': stream.get('codec_name'),
            'profile': stream.get('profile'),
            'width': stream.get('width'),
            'height': stream.get('height'),
            'frame_rate': stream.get('avg_frame_rate') or stream.get('r_frame_rate'),
            'bit_rate': stream.get('bit_rate'),
        })
    fmt = payload.get('format') or {}
    result['format'] = {
        'name': fmt.get('format_long_name') or fmt.get('format_name'),
        'bit_rate': fmt.get('bit_rate'),
        # Deliberately not fmt['filename'] — that is the URL, credentials and all.
        'url': redact_url(rtsp_url),
    }
    return result

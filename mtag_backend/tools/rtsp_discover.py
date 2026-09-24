"""Find the RTSP stream path a camera actually serves.

Every vendor invents its own path and none of them agree. Hikvision wants
/Streaming/Channels/101, Dahua wants /cam/realmonitor?channel=1&subtype=0,
Uniview wants /media/video1 — and a camera handed the wrong one answers
`404 Stream Not Found`, which reads like a broken camera and is not.

The distinction this exists to make, because it is the one people get wrong:

    401 Unauthorized  →  the PATH is fine, the CREDENTIALS are not
    404 Not Found     →  the CREDENTIALS are fine, the PATH is not
    no answer at all  →  wrong host or port, or a firewall

Speaks RTSP directly over a socket rather than shelling out to ffprobe: this has
to run on a booth, where ffmpeg may not be installed, and it is the tool someone
reaches for when the camera panel is not working. It needs nothing but the
standard library.

    python3 tools/rtsp_discover.py 192.168.78.21 --user admin --password 'Iteck@123'
    python3 tools/rtsp_discover.py rtsp://admin:Iteck%40123@192.168.78.21:554/wrong/path

The password is given in PLAIN form on the command line (or read from
RTSP_PASSWORD); percent-encoding is applied when the URL is built, so a password
with an @ in it needs no thought here.
"""

import argparse
import hashlib
import os
import re
import socket
import sys
import time
import urllib.parse

DEFAULT_PORT = 554
SOCKET_TIMEOUT = 4.0

# Ordered by how often they turn up on a toll lane. Each entry is
# (path, vendor) — the vendor label is what makes the result actionable, since
# knowing it is a Dahua tells you what the sub-stream path will be too.
CANDIDATE_PATHS = [
    ('/Streaming/Channels/101', 'Hikvision main'),
    ('/Streaming/Channels/102', 'Hikvision sub'),
    ('/cam/realmonitor?channel=1&subtype=0', 'Dahua / Amcrest main'),
    ('/cam/realmonitor?channel=1&subtype=1', 'Dahua / Amcrest sub'),
    ('/media/video1', 'Uniview main'),
    ('/media/video2', 'Uniview sub'),
    ('/unicast/c1/s0/live', 'Uniview (older)'),
    ('/h264/ch1/main/av_stream', 'Hikvision (older firmware)'),
    ('/h264/ch1/sub/av_stream', 'Hikvision sub (older firmware)'),
    ('/live/ch0', 'generic'),
    ('/live/ch1', 'generic'),
    ('/live.sdp', 'Vivotek'),
    ('/live1.sdp', 'Vivotek sub'),
    ('/axis-media/media.amp', 'Axis'),
    ('/h264Preview_01_main', 'Reolink main'),
    ('/h264Preview_01_sub', 'Reolink sub'),
    ('/stream1', 'TP-Link / Tapo main'),
    ('/stream2', 'TP-Link / Tapo sub'),
    ('/videoMain', 'Foscam main'),
    ('/videoSub', 'Foscam sub'),
    ('/profile1', 'ONVIF profile'),
    ('/profile2', 'ONVIF profile sub'),
    ('/onvif1', 'ONVIF generic'),
    ('/MediaInput/h264', 'Panasonic'),
    ('/rtsp_tunnel', 'Bosch'),
    ('/video1', 'Sony / generic'),
    ('/11', 'XMEye / generic'),
    ('/ch0_0.h264', 'generic'),
    ('/live', 'generic'),
    ('/', 'server root'),
]


class RtspError(Exception):
    pass


def _digest_response(user, password, realm, nonce, method, uri):
    def md5(text):
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    ha1 = md5(f'{user}:{realm}:{password}')
    ha2 = md5(f'{method}:{uri}')
    return md5(f'{ha1}:{nonce}:{ha2}')


def _auth_header(challenge, user, password, method, uri):
    """Build the Authorization header for whichever scheme was demanded."""
    if not challenge:
        return ''
    scheme = challenge.split(None, 1)[0].lower()
    if scheme == 'basic':
        import base64
        token = base64.b64encode(f'{user}:{password}'.encode()).decode()
        return f'Basic {token}'
    if scheme == 'digest':
        realm = re.search(r'realm="([^"]*)"', challenge)
        nonce = re.search(r'nonce="([^"]*)"', challenge)
        if not realm or not nonce:
            return ''
        response = _digest_response(
            user, password, realm.group(1), nonce.group(1), method, uri)
        return (f'Digest username="{user}", realm="{realm.group(1)}", '
                f'nonce="{nonce.group(1)}", uri="{uri}", response="{response}"')
    return ''


class RtspProbe:
    """One TCP connection, reused across every path tried.

    Reconnecting per path would turn a 30-path sweep into 30 handshakes, and
    some cameras rate-limit or briefly lock out a client that does that.
    """

    def __init__(self, host, port=DEFAULT_PORT, user='', password='',
                 timeout=SOCKET_TIMEOUT):
        self.host = host
        self.port = int(port)
        self.user = user
        self.password = password
        self.timeout = timeout
        self.sock = None
        self.cseq = 0
        self.challenge = ''
        self.server = ''

    def connect(self):
        self.sock = socket.create_connection((self.host, self.port), self.timeout)
        self.sock.settimeout(self.timeout)

    def close(self):
        try:
            if self.sock:
                self.sock.close()
        except OSError:
            pass
        self.sock = None

    def _request(self, method, path, extra_headers=''):
        """Send one request, retrying once with credentials on a 401."""
        uri = f'rtsp://{self.host}:{self.port}{path}'
        for attempt in (1, 2):
            self.cseq += 1
            auth = _auth_header(self.challenge, self.user, self.password, method, uri)
            lines = [
                f'{method} {uri} RTSP/1.0',
                f'CSeq: {self.cseq}',
                'User-Agent: mtag-rtsp-discover',
            ]
            if auth:
                lines.append(f'Authorization: {auth}')
            if extra_headers:
                lines.append(extra_headers)
            message = '\r\n'.join(lines) + '\r\n\r\n'

            try:
                self.sock.sendall(message.encode())
                response = self._read_response()
            except (OSError, socket.timeout) as exc:
                # Some cameras drop the connection after a 404. Reconnect once
                # so one bad path does not end the sweep.
                self.close()
                if attempt == 2:
                    raise RtspError(str(exc))
                self.connect()
                continue

            status = self._status(response)
            server = re.search(r'(?im)^Server:\s*(.+)$', response)
            if server and not self.server:
                self.server = server.group(1).strip()

            if status == 401 and attempt == 1:
                found = re.search(r'(?im)^WWW-Authenticate:\s*(.+)$', response)
                if found and self.user:
                    self.challenge = found.group(1).strip()
                    continue
            return status, response
        return 0, ''

    def _read_response(self):
        data = b''
        deadline = time.monotonic() + self.timeout
        while b'\r\n\r\n' not in data:
            if time.monotonic() > deadline:
                raise RtspError('timed out waiting for a reply')
            chunk = self.sock.recv(4096)
            if not chunk:
                raise RtspError('connection closed by the camera')
            data += chunk
        head, _, rest = data.partition(b'\r\n\r\n')
        text = head.decode('utf-8', 'replace')
        # Pull in the SDP body when the camera said how long it is, so the
        # resolution can be reported alongside a working path.
        length = re.search(r'(?im)^Content-Length:\s*(\d+)', text)
        if length:
            want = int(length.group(1))
            while len(rest) < want:
                try:
                    chunk = self.sock.recv(4096)
                except (OSError, socket.timeout):
                    break
                if not chunk:
                    break
                rest += chunk
            text += '\r\n\r\n' + rest[:want].decode('utf-8', 'replace')
        return text

    @staticmethod
    def _status(response):
        match = re.match(r'RTSP/\d\.\d\s+(\d+)', response or '')
        return int(match.group(1)) if match else 0

    def options(self):
        return self._request('OPTIONS', '/')

    def describe(self, path):
        return self._request('DESCRIBE', path, 'Accept: application/sdp')


def summarise_sdp(response):
    """Codec and resolution out of the SDP, when the camera volunteered them."""
    details = []
    media = re.findall(r'(?im)^m=(\w+)\s', response)
    rtpmap = re.findall(r'(?im)^a=rtpmap:\d+\s+([\w-]+)', response)
    if rtpmap:
        details.append('/'.join(dict.fromkeys(rtpmap)))
    elif media:
        details.append('/'.join(dict.fromkeys(media)))
    size = re.search(r'(?im)^a=x-dimensions:\s*(\d{3,5})\s*,\s*(\d{3,5})', response)
    if not size:
        size = re.search(r'(?i)\b(\d{3,5})x(\d{3,5})\b', response)
    if size:
        details.append(f'{size.group(1)}x{size.group(2)}')
    framerate = re.search(r'(?im)^a=framerate:([\d.]+)', response)
    if framerate:
        details.append(f'{framerate.group(1)} fps')
    return ' · '.join(details)


def build_url(host, port, user, password, path):
    """The URL to put in rfid_config.ini, correctly percent-encoded.

    `quote` with safe='' encodes @ as %40, : as %3A and so on. ffmpeg decodes
    the userinfo again before authenticating (verified against ffmpeg 7.0), so
    the camera receives the password exactly as typed here.
    """
    if user:
        creds = urllib.parse.quote(user, safe='')
        if password:
            creds += ':' + urllib.parse.quote(password, safe='')
        creds += '@'
    else:
        creds = ''
    port_part = '' if int(port) == DEFAULT_PORT else f':{port}'
    return f'rtsp://{creds}{host}{port_part}{path}'


def discover(host, port=DEFAULT_PORT, user='', password='',
             paths=None, timeout=SOCKET_TIMEOUT, stop_on_first=False,
             budget=None):
    """Try each candidate path. Returns a dict the console and the CLI share.

    `budget` caps the whole sweep in seconds. A camera that silently drops what
    it does not recognise costs one full timeout per path, and thirty of those
    is two minutes — far too long for a browser request. When the budget runs
    out the paths tried so far are returned with `truncated` set, which is a
    useful answer rather than a failed one.
    """
    result = {
        'host': host, 'port': int(port), 'server': '',
        'reachable': False, 'authenticated': None,
        'working': [], 'tried': [], 'error': '', 'truncated': False,
    }
    deadline = (time.monotonic() + budget) if budget else None
    probe = RtspProbe(host, port, user, password, timeout)
    try:
        probe.connect()
    except OSError as exc:
        result['error'] = (
            f'cannot reach {host}:{port} — {exc}. Check the address, the port, '
            f'and that this machine is on the same network as the camera.'
        )
        return result
    result['reachable'] = True

    try:
        status, _ = probe.options()
        result['server'] = probe.server
        # A 401 that survives the retry means the credentials are wrong, and
        # every path would then answer 401 too — say so once instead of
        # thirty times.
        if status == 401:
            result['authenticated'] = False
            result['error'] = (
                'the camera rejected these credentials (401). The path cannot be '
                'tested until they are right — check the username and password, '
                'and give the password in plain form here, not percent-encoded.'
            )
            return result
        result['authenticated'] = True

        for path, vendor in (paths or CANDIDATE_PATHS):
            if deadline and time.monotonic() > deadline:
                result['truncated'] = True
                break
            try:
                status, response = probe.describe(path)
            except RtspError as exc:
                result['tried'].append(
                    {'path': path, 'vendor': vendor, 'status': 0, 'note': str(exc)})
                continue
            entry = {'path': path, 'vendor': vendor, 'status': status, 'note': ''}
            if status == 200:
                entry['note'] = summarise_sdp(response)
                entry['url'] = build_url(host, port, user, password, path)
                result['working'].append(entry)
                if stop_on_first:
                    result['tried'].append(entry)
                    break
            elif status == 401:
                # Some cameras authorise per stream rather than per connection.
                entry['note'] = 'credentials rejected for this path'
                result['authenticated'] = False
            result['tried'].append(entry)
    finally:
        probe.close()

    if not result['working'] and result['truncated']:
        result['error'] = (
            f'gave up after {len(result["tried"])} paths — the camera is not '
            f'answering quickly enough to sweep the rest. Try the command-line '
            f'tool, which has no request deadline: '
            f'python3 tools/rtsp_discover.py {host} --user <user> --password <pass>'
        )
    if not result['working'] and not result['error']:
        result['error'] = (
            'the camera answered but none of the known paths worked. Open '
            f'http://{host}/ in a browser — the path is usually printed in the '
            "network or RTSP settings — or check the model's manual."
        )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Find the RTSP stream path a camera actually serves.')
    parser.add_argument('target', help='camera IP/hostname, or a full rtsp:// URL')
    parser.add_argument('--user', default='', help='username (default: admin)')
    parser.add_argument('--password', default=os.environ.get('RTSP_PASSWORD', ''),
                        help='password IN PLAIN FORM, or set RTSP_PASSWORD')
    parser.add_argument('--port', type=int, default=None)
    parser.add_argument('--timeout', type=float, default=SOCKET_TIMEOUT)
    parser.add_argument('--first', action='store_true',
                        help='stop at the first path that works')
    parser.add_argument('--budget', type=float, default=None,
                        help='give up after this many seconds (default: no limit)')
    args = parser.parse_args(argv)

    host, port, user, password = args.target, args.port, args.user, args.password
    if '://' in args.target:
        parsed = urllib.parse.urlparse(args.target)
        host = parsed.hostname or ''
        port = port or parsed.port or DEFAULT_PORT
        # Credentials in a URL are percent-encoded; unquote them back to plain.
        user = user or urllib.parse.unquote(parsed.username or '')
        password = password or urllib.parse.unquote(parsed.password or '')
    port = port or DEFAULT_PORT
    user = user or 'admin'

    print(f'Probing {host}:{port} as {user or "(anonymous)"} …\n')
    result = discover(host, port, user, password, timeout=args.timeout,
                      stop_on_first=args.first, budget=args.budget)

    if result['server']:
        print(f'  Server: {result["server"]}')
    if not result['reachable'] or result['authenticated'] is False:
        print(f'\n  ✗ {result["error"]}')
        return 2

    for entry in result['tried']:
        mark = '✓' if entry['status'] == 200 else ' '
        status = entry['status'] or '--'
        note = f'  {entry["note"]}' if entry['note'] else ''
        print(f'  {mark} {str(status):>4}  {entry["path"]:<42} {entry["vendor"]}{note}')

    if not result['working']:
        print(f'\n  ✗ {result["error"]}')
        return 1

    print(f'\n  {len(result["working"])} working path(s). Put this in '
          f'rfid_config.ini under [camera]:\n')
    for entry in result['working']:
        print(f'    rtsp_url = {entry["url"]}')
        print(f'    # {entry["vendor"]}' + (f' — {entry["note"]}' if entry['note'] else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())

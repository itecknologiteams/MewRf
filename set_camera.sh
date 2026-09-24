#!/usr/bin/env bash
# Add the [camera] section to every booth's rfid_config.ini.
#
# Run on your dev machine, on the LAN/VPN that reaches the booths. Same shape as
# set_rssi.sh: booth list from master's database unless you name booths, a .bak
# left on each booth, and a summary at the end.
#
#   ./set_camera.sh                              # add a blank [camera] everywhere
#   ./set_camera.sh --dry-run                    # show the result, change nothing
#   ./set_camera.sh --url-map cameras.txt        # and set each booth's own URL
#   ./set_camera.sh 192.168.78.19 --url 'rtsp://admin:Iteck%40123@192.168.78.21:554/profile1'
#
# THIS DOES NOT TOUCH THE LANE. run_gate never reads [camera] — only the booth
# console does — so nothing here restarts mtag-gate and no barrier stops working
# while it runs. Only mtag-web is restarted, and only so the console picks the
# new values up.
#
# The section is written idempotently: values already on a booth are kept, the
# comment block is refreshed, and running it twice changes nothing the second
# time. Safe to re-run after a deploy.
#
# ── Per-booth URLs ───────────────────────────────────────────────────────────
# Every lane has its own camera, so there is no single fleet-wide URL. Either
# leave rtsp_url blank here and set it per booth in the console's Reader Config
# tab, or pass a map file of "booth_ip  rtsp_url" lines:
#
#     # cameras.txt — one line per booth, '#' comments allowed
#     192.168.78.19   rtsp://admin:Iteck%40123@192.168.78.21:554/profile1
#     192.168.78.20   rtsp://admin:Iteck%40123@192.168.78.22:554/profile1
#
# KEEP THAT FILE OUT OF GIT — it holds camera passwords. .gitignore already
# covers cameras.txt and *.cameras.
#
# PERCENT-ENCODE the password: a literal '@' ends the userinfo and the rest
# parses as the hostname. Iteck@123 is written Iteck%40123 (@ = %40, : = %3A,
# / = %2F, space = %20). ffmpeg decodes it again before authenticating.
#
# Flags:
#   --url-map FILE     per-booth URLs, "booth_ip  rtsp_url" lines
#   --url URL          one URL, only valid with exactly one booth named
#   --stream-url URL   low-resolution sub-stream for the live view (see below)
#   --width N --fps N --quality N   live-view output (defaults 640 / 6 / 7)
#   --clear-url        blank rtsp_url on the named booths
#   --dry-run          print the resulting [camera] block, change nothing
#   --no-restart       write the config but leave mtag-web alone
#   --user USER --port PORT   SSH user/port (defaults below)

set -uo pipefail

MASTER_HOST="${MASTER_HOST:-103.7.60.67}"
MASTER_SSH_USER="${MASTER_SSH_USER:-mew02}"
MASTER_SSH_PORT="${MASTER_SSH_PORT:-1122}"
MASTER_DIR="${MASTER_DIR:-mtag_backend}"
MASTER_SSH_PASSWORD="${MASTER_SSH_PASSWORD:-}"

SSH_USER="iteck"
SSH_PORT="22"
REMOTE_DIR="mtag_backend"
# Same contract as deploy_booths.sh: -e keeps the password out of argv.
SSH_PASSWORD="${BOOTH_SSH_PASSWORD:-}"

URL_MAP="" SINGLE_URL="" STREAM_URL="" CLEAR_URL=0
WIDTH="640" FPS="6" QUALITY="7"
DRY_RUN=0 RESTART=1
TARGETS=()

while [ $# -gt 0 ]; do
  case "$1" in
    --url-map)    URL_MAP="$2";    shift 2 ;;
    --url)        SINGLE_URL="$2"; shift 2 ;;
    --stream-url) STREAM_URL="$2"; shift 2 ;;
    --width)      WIDTH="$2";      shift 2 ;;
    --fps)        FPS="$2";        shift 2 ;;
    --quality)    QUALITY="$2";    shift 2 ;;
    --clear-url)  CLEAR_URL=1;     shift ;;
    --dry-run)    DRY_RUN=1;       shift ;;
    --no-restart) RESTART=0;       shift ;;
    --user)       SSH_USER="$2";   shift 2 ;;
    --port)       SSH_PORT="$2";   shift 2 ;;
    -h|--help)    sed -n '2,47p' "$0"; exit 0 ;;
    -*)           echo "ERROR: unknown flag $1" >&2; exit 1 ;;
    *)            TARGETS+=("$1"); shift ;;
  esac
done

# ── Validate here, before any booth is touched ───────────────────────────────
if [ -n "$SINGLE_URL" ] && [ -n "$URL_MAP" ]; then
  echo "ERROR: --url and --url-map are alternatives, not both." >&2; exit 1
fi
if [ -n "$SINGLE_URL" ] && [ ${#TARGETS[@]} -ne 1 ]; then
  echo "ERROR: --url sets ONE booth's camera, so name exactly one booth." >&2
  echo "       For a fleet, use --url-map. Each lane has its own camera." >&2
  exit 1
fi
if [ -n "$URL_MAP" ] && [ ! -r "$URL_MAP" ]; then
  echo "ERROR: cannot read url map '$URL_MAP'." >&2; exit 1
fi

check_url() {
  local url="$1" label="$2"
  [ -z "$url" ] && return 0
  case "$url" in
    rtsp://*|rtsps://*|http://*|https://*) ;;
    *) echo "ERROR: $label must start with rtsp:// (or http://), got '$url'" >&2; return 1 ;;
  esac
  # Two '@' means the password has a literal one. The userinfo ends at the LAST
  # '@', so the host would be parsed out of the middle of the password and the
  # camera would refuse the login with no clue why.
  local ats="${url//[^@]/}"
  if [ ${#ats} -gt 1 ]; then
    echo "ERROR: $label has more than one '@' — percent-encode the password." >&2
    echo "       A password of Iteck@123 is written Iteck%40123." >&2
    return 1
  fi
  return 0
}
check_url "$SINGLE_URL" "--url" || exit 1
check_url "$STREAM_URL" "--stream-url" || exit 1

python3 -c '
import sys
w, f, q = int(sys.argv[1]), float(sys.argv[2]), int(sys.argv[3])
errs = []
if not 160 <= w <= 1920:   errs.append("--width must be 160-1920")
if not 0.5 <= f <= 15:     errs.append("--fps must be 0.5-15")
if not 2 <= q <= 31:       errs.append("--quality must be 2-31 (2 best, 31 worst)")
for e in errs: print("ERROR: " + e, file=sys.stderr)
sys.exit(1 if errs else 0)
' "$WIDTH" "$FPS" "$QUALITY" || exit 1

if [ -n "$URL_MAP" ]; then
  while read -r ip url _rest; do
    [ -z "${ip:-}" ] && continue
    case "$ip" in \#*) continue ;; esac
    check_url "$url" "url for $ip" || exit 1
  done < "$URL_MAP"
  echo "--- url map '$URL_MAP' validated ---"
fi

# ── The remote edit ──────────────────────────────────────────────────────────
# configparser would drop every comment in the file, so the [camera] section is
# cut out line by line and one canonical block written in its place. Existing
# values are read back first and preserved, which is what makes a re-run a
# no-op. Written to a temp file and os.replace'd, so a booth losing power
# mid-write keeps the old config rather than half of a new one.
REMOTE_PY=$(cat <<'PY'
import configparser, io, os, sys

path, rtsp, stream, width, fps, quality, clear_url, dry = sys.argv[1:9]

try:
    original = open(path).read()
except FileNotFoundError:
    print(f"NO CONFIG: {path} does not exist", file=sys.stderr); sys.exit(3)

lines = original.splitlines()

# A file with no [gate] section is not a config the gate can run from; adding a
# [camera] block to it would hide that behind a success line.
if not any(l.strip().lower() == '[gate]' for l in lines):
    print(f"BAD CONFIG: {path} has no [gate] section", file=sys.stderr); sys.exit(5)

# interpolation=None: a camera password is percent-encoded, and '%' is a
# substitution marker to configparser's default parser.
existing = {}
had_section = False
parser = configparser.ConfigParser(interpolation=None)
try:
    parser.read_string(original)
    if parser.has_section('camera'):
        had_section = True
        existing = dict(parser['camera'])
except configparser.Error as exc:
    print(f"BAD CONFIG: {path} will not parse: {exc}", file=sys.stderr); sys.exit(5)

def pick(key, override, default=''):
    """An explicit value wins; otherwise keep what the booth already has."""
    if override:
        return override
    return existing.get(key, default)

values = {
    'rtsp_url': '' if clear_url == '1' else pick('rtsp_url', rtsp),
    'transport': existing.get('transport', 'tcp'),
    'snapshot_url': existing.get('snapshot_url', ''),
    'stream_url': pick('stream_url', stream),
    'stream_width': width or existing.get('stream_width', '640'),
    'stream_fps': fps or existing.get('stream_fps', '6'),
    'stream_quality': quality or existing.get('stream_quality', '7'),
}

block = f"""[camera]
# LPR / ANPR camera, for the booth console at /booth/ . Plate recognition itself
# runs in quick-toll-system (run_anpr_gate subscribes to its WebSocket on :3003)
# — this is only so an engineer at the lane can confirm the camera is up, aimed
# and in focus without leaving the console.
#
# NOTHING HERE IS READ BY run_gate. Changing it cannot stop a barrier opening,
# and only mtag-web needs restarting to pick it up.
#
# PERCENT-ENCODE anything special in the password. A literal '@' would end the
# userinfo and the host would parse as the rest of the password, so a password
# of Iteck@123 is written Iteck%40123. Verified against ffmpeg 7.0: it decodes
# the userinfo before authenticating, so the camera receives Iteck@123.
# Common ones: @ = %40, : = %3A, / = %2F, ? = %3F, # = %23, space = %20.
# Leave rtsp_url blank to hide the panel.
rtsp_url = {values['rtsp_url']}
# tcp is right almost always: UDP loses packets over a booth's wiring and shows
# as a torn frame that looks like a camera fault.
transport = {values['transport']}
# Optional. If the camera already serves a JPEG over HTTP, the console prefers
# it — it is far cheaper than spinning ffmpeg up for every frame.
snapshot_url = {values['snapshot_url']}

# ── Live view ────────────────────────────────────────────────────────────────
# The console can play a live picture, not just stills. No browser plays RTSP and
# Chrome will not decode H.265, so the booth transcodes to MJPEG — which costs
# CPU on a machine that also has a lane to run. These bound that cost.
#
# stream_url is the single biggest saving available: most cameras publish a
# low-resolution SUB-STREAM beside the main one, and transcoding that costs a
# fraction of transcoding 1080p. The panel cannot show the difference.
#   Hikvision  /Streaming/Channels/102      Dahua  ...&subtype=1
#   ONVIF      /profile2                    Uniview  /media/video2
# Leave blank to use rtsp_url.
stream_url = {values['stream_url']}
# Output width; the height follows the aspect ratio. 160-1920.
stream_width = {values['stream_width']}
# Frames per second, 0.5-15. Six is smooth enough to watch a vehicle through.
stream_fps = {values['stream_fps']}
# ffmpeg -q:v — 2 is best and largest, 31 is worst and smallest.
stream_quality = {values['stream_quality']}
#
# Caps enforced in code, not here: one shared ffmpeg however many people watch,
# at most 2 viewers (each holds one of gunicorn's four threads), the transcode
# stops 5s after the last viewer leaves, and any stream ends after 10 minutes.""".splitlines()

# Cut the old [camera] section out, wherever it sits, then append the new one.
out, in_camera = [], False
for line in lines:
    stripped = line.strip()
    if stripped.startswith('[') and stripped.endswith(']'):
        in_camera = stripped.lower() == '[camera]'
        if in_camera:
            continue
    if in_camera:
        continue
    out.append(line)

while out and not out[-1].strip():
    out.pop()
out.append('')
out.extend(block)

text = '\n'.join(out).rstrip('\n') + '\n'

# Prove the result parses before it replaces anything. A malformed ini is read
# by the console on every request and by the gate on every restart.
check = configparser.ConfigParser(interpolation=None)
try:
    check.read_string(text)
    check.get('camera', 'rtsp_url')
    check.get('gate', 'mode')
except configparser.Error as exc:
    print(f"REFUSED: the rewritten file would not parse: {exc}", file=sys.stderr)
    sys.exit(6)

if dry == '1':
    for ln in block:
        print('    ' + ln)
    sys.exit(0)

if text == original:
    print(f"    unchanged (already correct)")
    sys.exit(0)

with open(path + '.bak', 'w') as f:
    f.write(original)
tmp = path + '.tmp'
with open(tmp, 'w') as f:
    f.write(text); f.flush(); os.fsync(f.fileno())
os.replace(tmp, path)

shown = values['rtsp_url'] or '(blank — set it in the console)'
if '@' in shown:
    head, _, tail = shown.rpartition('@')
    user = head.split('//')[-1].split(':')[0]
    shown = f"{head.split('//')[0]}//{user}:********@{tail}"
verb = 'updated' if had_section else 'added'
print(f"    [camera] {verb} — rtsp_url = {shown}")
PY
)
REMOTE_PY_B64=$(printf '%s' "$REMOTE_PY" | base64 -w0)

master_ssh() {
  local ssh_opts=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=10
                  -p "$MASTER_SSH_PORT")
  if [ -n "$MASTER_SSH_PASSWORD" ]; then
    command -v sshpass >/dev/null 2>&1 || {
      echo "ERROR: MASTER_SSH_PASSWORD is set but sshpass is not installed." >&2; return 1; }
    ( export SSHPASS="$MASTER_SSH_PASSWORD"
      sshpass -e ssh -n "${ssh_opts[@]}" "$MASTER_SSH_USER@$MASTER_HOST" "$1" )
  else
    ssh -n "${ssh_opts[@]}" "$MASTER_SSH_USER@$MASTER_HOST" "$1"
  fi
}

if [ ${#TARGETS[@]} -eq 0 ]; then
  echo "--- fetching booth list from master ($MASTER_SSH_USER@$MASTER_HOST) ---"
  BOOTH_LIST="$(master_ssh "cd $MASTER_DIR && DJANGO_SETTINGS_MODULE=config.settings.lan venv/bin/python manage.py list_booths" 2>/dev/null)" || BOOTH_LIST=""
  if [ -z "$BOOTH_LIST" ]; then
    echo "ERROR: master returned no booth addresses — name the booths explicitly." >&2
    exit 1
  fi
  readarray -t TARGETS <<<"$BOOTH_LIST"
  echo "    ${#TARGETS[@]} booth(s) recorded on master"
fi

url_for() {
  local ip="$1"
  if [ -n "$SINGLE_URL" ]; then printf '%s' "$SINGLE_URL"; return; fi
  [ -z "$URL_MAP" ] && return
  while read -r map_ip map_url _rest; do
    [ -z "${map_ip:-}" ] && continue
    case "$map_ip" in \#*) continue ;; esac
    if [ "$map_ip" = "$ip" ]; then printf '%s' "$map_url"; return; fi
  done < "$URL_MAP"
}

SSH_WRAP=()
if [ -n "$SSH_PASSWORD" ]; then
  command -v sshpass >/dev/null 2>&1 || {
    echo "ERROR: BOOTH_SSH_PASSWORD is set but sshpass is not installed." >&2; exit 1; }
  export SSHPASS="$SSH_PASSWORD"
  SSH_WRAP=(sshpass -e)
fi

[ "$DRY_RUN" = "1" ] && echo "--- DRY RUN: nothing will be written ---"
echo "--- mtag-gate is NOT touched: run_gate never reads [camera] ---"

RESULTS=() FAILED=0
for BOOTH_IP in "${TARGETS[@]}"; do
  [ -z "$BOOTH_IP" ] && continue
  echo "═══ $BOOTH_IP ═══"
  BOOTH_URL="$(url_for "$BOOTH_IP")"
  CTL="$(mktemp -u /tmp/mtagcam-XXXXXXXX)"
  SSH_OPTS=(-o ControlMaster=auto -o "ControlPath=$CTL" -o ControlPersist=60
            -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 -p "$SSH_PORT")
  close_ctl() { ssh -O exit -o "ControlPath=$CTL" "$SSH_USER@$BOOTH_IP" 2>/dev/null; }

  # A percent-encoded URL is unreadable to a booth whose booth_probe.py still
  # uses configparser's default interpolation: it raises, the console catches it
  # as any other config error, and reports a fully configured camera as "not
  # configured". Catch that here, where it can be explained.
  if [ -n "$BOOTH_URL" ] && [[ "$BOOTH_URL" == *%* ]]; then
    HAS_FIX="$("${SSH_WRAP[@]}" ssh -n "${SSH_OPTS[@]}" "$SSH_USER@$BOOTH_IP" \
      "grep -lq 'interpolation=None' ~/$REMOTE_DIR/apps/tolls/booth_probe.py 2>/dev/null && echo yes || echo no")" || HAS_FIX="unknown"
    if [ "$HAS_FIX" = "no" ]; then
      RESULTS+=("NEEDS CODE  $BOOTH_IP — URL has '%' but booth_probe.py predates the interpolation fix; deploy the backend first")
      FAILED=1; close_ctl; continue
    fi
  fi

  "${SSH_WRAP[@]}" ssh -n "${SSH_OPTS[@]}" "$SSH_USER@$BOOTH_IP" "
    echo '$REMOTE_PY_B64' | base64 -d > /tmp/set_camera.py &&
    python3 /tmp/set_camera.py ~/$REMOTE_DIR/rfid_config.ini \
      '$BOOTH_URL' '$STREAM_URL' '$WIDTH' '$FPS' '$QUALITY' '$CLEAR_URL' '$DRY_RUN'
  "
  rc=$?
  if [ $rc -ne 0 ]; then
    case $rc in
      3)   RESULTS+=("NO CONFIG   $BOOTH_IP — rfid_config.ini missing; deploy it first") ;;
      5)   RESULTS+=("BAD CONFIG  $BOOTH_IP — rfid_config.ini is malformed or has no [gate]") ;;
      6)   RESULTS+=("REFUSED     $BOOTH_IP — the rewritten file would not parse; nothing written") ;;
      # ssh itself exits 255 when it cannot connect or authenticate. Reporting
      # that as "could not write the config" sends someone looking at the booth's
      # disk when the booth was never reached at all.
      255) RESULTS+=("UNREACHABLE $BOOTH_IP — ssh could not connect or authenticate (is BOOTH_SSH_PASSWORD set?)") ;;
      127) RESULTS+=("NO PYTHON   $BOOTH_IP — python3 not found on the booth") ;;
      *)   RESULTS+=("FAILED      $BOOTH_IP — remote edit exited $rc") ;;
    esac
    FAILED=1; close_ctl; continue
  fi

  if [ "$DRY_RUN" = "1" ]; then
    RESULTS+=("DRY RUN     $BOOTH_IP — nothing written"); close_ctl; continue
  fi
  if [ "$RESTART" = "0" ]; then
    RESULTS+=("OK          $BOOTH_IP — written (mtag-web NOT restarted)"); close_ctl; continue
  fi

  # Only mtag-web. The lane keeps running throughout: the gate is a separate PM2
  # app and does not read this section.
  echo "--- restarting mtag-web (the lane is unaffected) ---"
  STATUS="$("${SSH_WRAP[@]}" ssh -n "${SSH_OPTS[@]}" "$SSH_USER@$BOOTH_IP" "
    pm2 restart mtag-web >/dev/null 2>&1 || exit 4
    sleep 3
    pm2 jlist 2>/dev/null | python3 -c \"
import json,sys
for p in json.load(sys.stdin):
    if p['name'] == 'mtag-web':
        print(p['pm2_env']['status'])
        break
\"")" || STATUS=""

  case "$STATUS" in
    online*) RESULTS+=("OK          $BOOTH_IP — set, console reloaded") ;;
    "")      RESULTS+=("NO PM2      $BOOTH_IP — config set, but mtag-web could not be restarted"); FAILED=1 ;;
    *)       RESULTS+=("WEB DOWN    $BOOTH_IP — config set, mtag-web is '$STATUS' — check: pm2 logs mtag-web"); FAILED=1 ;;
  esac
  close_ctl
done

echo ""
echo "════════════════════ SUMMARY ════════════════════"
printf '%s\n' "${RESULTS[@]}"
if [ "$FAILED" = "1" ]; then
  echo ""
  echo "Roll a booth back with:  ssh $SSH_USER@<ip> 'cp ~/$REMOTE_DIR/rfid_config.ini.bak ~/$REMOTE_DIR/rfid_config.ini && pm2 restart mtag-web'"
fi
exit $FAILED

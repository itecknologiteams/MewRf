#!/usr/bin/env bash
# Set the RSSI staging thresholds in every booth's rfid_config.ini.
#
# Run on your dev machine, on the LAN/VPN that reaches the booths. Rewrites the
# [scanner] RSSI keys over SSH and restarts mtag-gate. Nothing else in the file
# is touched, and a .bak is left beside it on each booth.
#
#   ./set_rssi.sh --detect -70 --open-min -55 --open-max -52
#   ./set_rssi.sh --detect -70 --open-min -55 --open-max -52 192.168.78.61
#   ./set_rssi.sh --detect -70 --open-min -55 --open-max -52 --dry-run
#   ./set_rssi.sh --off                          # disable staging fleet-wide
#
# With no booths named, the list comes from master's database (the same source
# deploy_booths.sh uses), so a re-addressed booth is never missed here.
#
# THRESHOLDS ARE PER LANE. A band measured at one boom is a starting point
# elsewhere, not a fleet-wide truth — a band no vehicle reaches is a dead lane
# whose barrier never opens. Prefer naming booths explicitly; --dry-run first.
#
# Flags:
#   --detect N --open-min N --open-max N   dBm, negative, detect <= min <= max
#   --window N --hysteresis N              defaults 5 and 3.0
#   --off                                  all three thresholds to 0 (every read opens)
#   --dry-run                              print the resulting [scanner] block, change nothing
#   --no-restart                           write the config but leave mtag-gate alone
#   --user USER --port PORT                SSH user/port (defaults below)

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

DETECT="-65" OPEN_MIN="-55" OPEN_MAX="-45" WINDOW="5" HYST="3.0"
DRY_RUN=0 RESTART=1
TARGETS=()

while [ $# -gt 0 ]; do
  case "$1" in
    --detect)     DETECT="$2";   shift 2 ;;
    --open-min)   OPEN_MIN="$2"; shift 2 ;;
    --open-max)   OPEN_MAX="$2"; shift 2 ;;
    --window)     WINDOW="$2";   shift 2 ;;
    --hysteresis) HYST="$2";     shift 2 ;;
    --off)        DETECT=0; OPEN_MIN=0; OPEN_MAX=0; shift ;;
    --dry-run)    DRY_RUN=1; shift ;;
    --no-restart) RESTART=0; shift ;;
    --user)       SSH_USER="$2"; shift 2 ;;
    --port)       SSH_PORT="$2"; shift 2 ;;
    -h|--help)    sed -n '2,26p' "$0"; exit 0 ;;
    -*)           echo "ERROR: unknown flag $1" >&2; exit 1 ;;
    *)            TARGETS+=("$1"); shift ;;
  esac
done

if [ -z "$DETECT" ] || [ -z "$OPEN_MIN" ] || [ -z "$OPEN_MAX" ]; then
  echo "ERROR: --detect, --open-min and --open-max are all required (or --off)." >&2
  echo "       See ./set_rssi.sh --help" >&2
  exit 1
fi

# Validate HERE, before any booth is touched. run_gate refuses to start on a bad
# ordering, so pushing one fleet-wide would leave every gate crash-looping under
# PM2 with the barriers shut.
python3 -c '
import sys
d, lo, hi = float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3])
win, hys = int(sys.argv[4]), float(sys.argv[5])
errs = []
if win < 1:   errs.append("rssi_window must be >= 1")
if hys < 0:   errs.append("rssi_hysteresis must be >= 0")
if lo and hi and lo > hi:
    errs.append(f"open-min ({lo:g}) is above open-max ({hi:g}) — the barrier could never open")
if d and lo and d > lo:
    errs.append(f"detect ({d:g}) is above open-min ({lo:g}) — a vehicle would reach the "
                "barrier band before the gate noticed it; detect must be the more negative")
if any(v > 0 for v in (d, lo, hi)):
    errs.append("thresholds are dBm and must be negative (or 0 to disable)")
for e in errs: print("ERROR: " + e, file=sys.stderr)
sys.exit(1 if errs else 0)
' "$DETECT" "$OPEN_MIN" "$OPEN_MAX" "$WINDOW" "$HYST" || exit 1

# ── The remote edit ──────────────────────────────────────────────────────────
# configparser would rewrite the whole file and drop every comment, so the
# [scanner] section is edited line by line instead: the five keys and the two
# deprecated ones are removed along with their stale comments, then one fresh
# block is appended. Written to a temp file and os.replace'd, so a booth losing
# power mid-write keeps the old config rather than half of a new one.
REMOTE_PY=$(cat <<'PY'
import os, sys
path, d, lo, hi, win, hys, dry = sys.argv[1:8]
KEYS = ('rssi_detect', 'rssi_open_min', 'rssi_open_max',
        'rssi_window', 'rssi_hysteresis', 'rssi_filter', 'rssi_filter_max')
block = [
    "# Signal strength stands in for distance: closer vehicle, less negative dBm.",
    "#   weaker than rssi_detect        ignored (not in this lane yet)",
    "#   detect .. open_min             balance shown, nothing charged, barrier shut",
    "#   open_min .. open_max           trip charged, barrier opens",
    "# All three at 0 disables staging: every read opens.",
    f"rssi_detect = {d}",
    f"rssi_open_min = {lo}",
    f"rssi_open_max = {hi}",
    "# Jitter tolerance: the gate decides on the median of the last `rssi_window`",
    "# reads, and a tag at the barrier must fall `rssi_hysteresis` dB clear to be dropped.",
    f"rssi_window = {win}",
    f"rssi_hysteresis = {hys}",
]

try:
    lines = open(path).read().splitlines()
except FileNotFoundError:
    print(f"NO CONFIG: {path} does not exist", file=sys.stderr); sys.exit(3)

out, in_scanner, done, pending = [], False, False, []
for line in lines:
    stripped = line.strip()
    if stripped.startswith('['):
        if in_scanner and not done:
            out.extend(block); done = True
        # Comments sitting just above the next section header belong to it, not
        # to the block being replaced, so they are held back and re-emitted.
        out.extend(pending); pending = []
        in_scanner = stripped.lower() == '[scanner]'
        out.append(line); continue
    if in_scanner:
        key = stripped.split('=')[0].strip().lower()
        if key in KEYS:
            pending = []           # this key's own comments go with it
            continue
        if stripped.startswith(('#', ';')):
            if 'rssi' in stripped.lower():
                continue           # stale prose about keys being replaced
            pending.append(line); continue
        if not stripped:
            pending.append(line); continue
        out.extend(pending); pending = []
    out.append(line)
if in_scanner and not done:
    out.extend(block); done = True
out.extend(pending)

# No [scanner] section at all means this is not a config the gate can run from.
# Appending one would hide that behind a success line, so it is reported instead.
if not done:
    print(f"NO SCANNER SECTION: {path} has no [scanner] section", file=sys.stderr)
    sys.exit(5)

text = '\n'.join(out).rstrip('\n') + '\n'
if dry == '1':
    show = False
    for ln in text.splitlines():
        if ln.strip().startswith('['):
            show = ln.strip().lower() == '[scanner]'
        if show:
            print('    ' + ln)
    sys.exit(0)

if os.path.exists(path):
    with open(path + '.bak', 'w') as f:
        f.write(open(path).read())
tmp = path + '.tmp'
with open(tmp, 'w') as f:
    f.write(text); f.flush(); os.fsync(f.fileno())
os.replace(tmp, path)
print(f"    detect={d} open_min={lo} open_max={hi} window={win} hysteresis={hys}")
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

SSH_WRAP=()
if [ -n "$SSH_PASSWORD" ]; then
  command -v sshpass >/dev/null 2>&1 || {
    echo "ERROR: BOOTH_SSH_PASSWORD is set but sshpass is not installed." >&2; exit 1; }
  export SSHPASS="$SSH_PASSWORD"
  SSH_WRAP=(sshpass -e)
fi

[ "$DRY_RUN" = "1" ] && echo "--- DRY RUN: nothing will be written ---"

RESULTS=() FAILED=0
for BOOTH_IP in "${TARGETS[@]}"; do
  [ -z "$BOOTH_IP" ] && continue
  echo "═══ $BOOTH_IP ═══"
  CTL="$(mktemp -u /tmp/mtagrssi-XXXXXXXX)"
  SSH_OPTS=(-o ControlMaster=auto -o "ControlPath=$CTL" -o ControlPersist=60
            -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 -p "$SSH_PORT")

  "${SSH_WRAP[@]}" ssh -n "${SSH_OPTS[@]}" "$SSH_USER@$BOOTH_IP" "
    echo '$REMOTE_PY_B64' | base64 -d > /tmp/set_rssi.py &&
    python3 /tmp/set_rssi.py ~/$REMOTE_DIR/rfid_config.ini \
      '$DETECT' '$OPEN_MIN' '$OPEN_MAX' '$WINDOW' '$HYST' '$DRY_RUN'
  "
  rc=$?
  if [ $rc -ne 0 ]; then
    case $rc in
      3) RESULTS+=("NO CONFIG   $BOOTH_IP — rfid_config.ini missing; deploy it first") ;;
      5) RESULTS+=("BAD CONFIG  $BOOTH_IP — rfid_config.ini has no [scanner] section") ;;
      *) RESULTS+=("FAILED      $BOOTH_IP — could not write the config (rc=$rc)") ;;
    esac
    FAILED=1; ssh -O exit -o "ControlPath=$CTL" "$SSH_USER@$BOOTH_IP" 2>/dev/null; continue
  fi

  if [ "$DRY_RUN" = "1" ] || [ "$RESTART" = "0" ]; then
    RESULTS+=("OK          $BOOTH_IP — config written (gate NOT restarted)")
    [ "$DRY_RUN" = "1" ] && RESULTS[-1]="DRY RUN     $BOOTH_IP — nothing written"
    ssh -O exit -o "ControlPath=$CTL" "$SSH_USER@$BOOTH_IP" 2>/dev/null; continue
  fi

  # A bad threshold makes run_gate exit at startup, and PM2 keeps relaunching it.
  # Reading the status back is the only way that shows up here rather than as a
  # lane that quietly stopped opening.
  echo "--- restarting mtag-gate ---"
  STATUS="$("${SSH_WRAP[@]}" ssh -n "${SSH_OPTS[@]}" "$SSH_USER@$BOOTH_IP" "
    pm2 restart mtag-gate >/dev/null 2>&1 || exit 4
    sleep 4
    pm2 jlist 2>/dev/null | python3 -c \"
import json,sys
for p in json.load(sys.stdin):
    if p['name'] == 'mtag-gate':
        print(p['pm2_env']['status'], p['pm2_env'].get('restart_time', 0))
        break
\"")" || STATUS=""

  case "$STATUS" in
    online*) RESULTS+=("OK          $BOOTH_IP — set and gate online") ;;
    "")      RESULTS+=("NO PM2      $BOOTH_IP — config set, but mtag-gate could not be restarted"); FAILED=1 ;;
    *)       RESULTS+=("GATE DOWN   $BOOTH_IP — config set, gate is '$STATUS' — check: pm2 logs mtag-gate"); FAILED=1 ;;
  esac
  ssh -O exit -o "ControlPath=$CTL" "$SSH_USER@$BOOTH_IP" 2>/dev/null
done

echo ""
echo "════════════════════ SUMMARY ════════════════════"
printf '%s\n' "${RESULTS[@]}"
[ "$FAILED" = "1" ] && echo "" && echo "Roll a booth back with:  ssh $SSH_USER@<ip> 'cp ~/$REMOTE_DIR/rfid_config.ini.bak ~/$REMOTE_DIR/rfid_config.ini && pm2 restart mtag-gate'"
exit $FAILED

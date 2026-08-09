#!/usr/bin/env bash
# Run THIS on your dev machine (with the VPN/LAN connection to the booth).
# Builds a fresh mtag_backend tarball, copies it to the booth, and runs
# mtag_backend/booth_bootstrap.sh there to configure + start everything.
#
# Interactive (prompts for anything not already set):
#   ./deploy_booth.sh
#
# Or non-interactive, e.g. for scripting several booths in a row:
#   BOOTH_IP=192.168.78.21 SSH_USER=mew02 SSH_PORT=1122 \
#   BOOTH_NUMBER=3 PLAZA_ID=3 GATE_MODE=exit LANE_NUMBER=11 \
#   READER_IP=192.168.78.14 DB_PASSWORD=xxxx MASTER_DB_NAME=master_tag_db \
#   ./deploy_booth.sh
#
# GATE_MODE must be "entry" or "exit" — get this right per booth, it's not
# inferrable from BOOTH_NUMBER/LANE_NUMBER alone.
#
# Caveat: DB_PASSWORD is passed over SSH as part of a command line, so it's
# briefly visible via `ps` on both ends during the run. Fine for a private
# VPN/LAN deployment tool; don't reuse this for anything internet-facing.
# Avoid single-quote characters in DB_PASSWORD — the quoting below doesn't
# escape them.

set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# FILLED IN for this booth. Change these for the next booth, or blank any of
# them out ("") to be asked for it interactively instead when the script runs.
# ─────────────────────────────────────────────────────────────────────────────
BOOTH_IP="192.168.78.19"        # this booth's LAN IP (SSH target)
SSH_USER="iteck"               # SSH username on the booth
SSH_PORT="22"                  # SSH port
BOOTH_NUMBER="04"              # this booth's number
PLAZA_ID="001"                   # integer Plaza.plaza_id. Operator numbering:
                               #   1  = 001 Shahfaisal Main Toll Plaza
                               #   2  = 002 Kathor Main Toll Plaza
                               #   101 = Shafaisal-1     102 = Shafaisal-2
                               #   103 = Korangi 1       104 = Korangi 2
                               #   105 = Quaidabad       106 = Quaidabad
                               #   107 = Mai Niyari
                               # NOTE leading zeros are display-only — 001 is the
                               # integer 1. SET THIS PER BOOTH; the default below
                               # is a guess, and a wrong value tolls the wrong plaza.
                               # Must already exist on master (run load_plazas there).
GATE_MODE="entry"              # "entry" or "exit" — must match this booth's actual lane
READER_IP="192.168.78.20"      # RFID reader's own IP
LANE_NUMBER="04"               # this booth's TollLane.lane_number at plaza 3.
                               # Only correct because this is an entry booth — an
                               # exit booth's lane number is NOT its booth number.
DISPLAY_IP="192.168.78.24"     # UFD (display) IP
BARRIER_PORT="/dev/ttyUSB0"    # serial port the barrier is wired to
MASTER_IP="192.168.78.200"     # master server's LAN IP
MASTER_DB_NAME="master_tag_db" # master's database name
MASTER_DB_USER="postgres"      # master's DB user
MASTER_DB_PASSWORD=""          # master's DB password — MUST match what you gave
                               # deploy_master.sh. Deliberately blank: a stale
                               # baked-in value is worse than an empty one,
                               # because the prompt below re-asks for it while a
                               # wrong default gets accepted silently and the
                               # booth's sync then cannot authenticate.
DB_NAME="tag_db"               # this booth's own local DB name
DB_USER="postgres"             # this booth's own local DB user
DB_PASSWORD="12345678"         # this booth's own local DB password
# ─────────────────────────────────────────────────────────────────────────────

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARBALL="$REPO_ROOT/mtag_backend_deploy.tar.gz"

prompt() {
  local var="$1" msg="$2" default="${3:-}"
  if [ -z "${!var:-}" ]; then
    read -rp "$msg${default:+ [$default]}: " val
    export "$var"="${val:-$default}"
  fi
}

echo "=== Booth deployment ==="
prompt BOOTH_IP        "Booth LAN IP"
prompt SSH_USER        "SSH username"
prompt SSH_PORT        "SSH port" "22"
prompt BOOTH_NUMBER    "Booth number"
prompt PLAZA_ID        "Plaza ID (integer)"
if ! printf '%s' "$PLAZA_ID" | grep -qE '^[0-9]+$'; then
  echo "ERROR: PLAZA_ID must be an integer plaza number (e.g. 3), got '$PLAZA_ID'" >&2
  exit 1
fi
prompt GATE_MODE       "Gate mode (entry/exit)" "entry"
if [ "$GATE_MODE" != "entry" ] && [ "$GATE_MODE" != "exit" ]; then
  echo "ERROR: GATE_MODE must be 'entry' or 'exit', got '$GATE_MODE'" >&2
  exit 1
fi
prompt READER_IP       "RFID reader IP"
prompt LANE_NUMBER     "Lane number" "$BOOTH_NUMBER"
prompt DISPLAY_IP      "UFD (display) IP" "192.168.78.72"
prompt BARRIER_PORT    "Barrier serial port" "/dev/ttyUSB0"
prompt MASTER_IP       "Master server LAN IP" "192.168.78.200"
prompt MASTER_DB_NAME  "Master's database name" "master_tag_db"
prompt MASTER_DB_USER  "Master's DB user" "postgres"
prompt MASTER_DB_PASSWORD "Master's DB password"
if [ -z "$MASTER_DB_PASSWORD" ]; then
  echo "ERROR: master's DB password is required — the booth's sync authenticates" >&2
  echo "       to master with it. It must match what you gave deploy_master.sh." >&2
  exit 1
fi
prompt DB_NAME         "This booth's local DB name" "tag_db"
prompt DB_USER         "This booth's local DB user" "postgres"
prompt DB_PASSWORD     "This booth's local DB password"

echo ""
echo "--- Building fresh tarball from $REPO_ROOT/mtag_backend ---"
cd "$REPO_ROOT"
tar -czf "$TARBALL" \
  --exclude='venv' \
  --exclude='staticfiles' \
  --exclude='__pycache__' \
  --exclude='.env' \
  --exclude='rfid_config.ini' \
  --exclude='offline_cache.db' \
  --exclude='*.pyc' \
  mtag_backend
ls -lh "$TARBALL"

echo "--- Copying to $SSH_USER@$BOOTH_IP:$SSH_PORT ---"
scp -P "$SSH_PORT" "$TARBALL" "$SSH_USER@$BOOTH_IP:~/"

echo "--- Extracting code on the booth ---"
ssh -p "$SSH_PORT" "$SSH_USER@$BOOTH_IP" "tar -xzf mtag_backend_deploy.tar.gz"

# No venv transfer needed — the RFID SDK is vendored directly into
# mtag_backend/vendor/rfid_sdk/ (part of the code tarball above), and
# booth_bootstrap.sh installs it into whatever venv it creates/finds.

echo "--- Bootstrapping on the booth ---"
echo "(booth_bootstrap.sh runs several 'sudo' commands remotely — enter the"
echo " booth's sudo password below if/when prompted)"
# -t allocates a pseudo-terminal so `sudo` on the remote end can actually
# prompt for a password through this piped command — without it, sudo just
# fails with "a password is required" instead of asking.
# shellcheck disable=SC2087
ssh -t -p "$SSH_PORT" "$SSH_USER@$BOOTH_IP" "
  cd mtag_backend &&
  BOOTH_NUMBER='$BOOTH_NUMBER' \
  PLAZA_ID='$PLAZA_ID' \
  GATE_MODE='$GATE_MODE' \
  LANE_NUMBER='$LANE_NUMBER' \
  READER_IP='$READER_IP' \
  DISPLAY_IP='$DISPLAY_IP' \
  BARRIER_PORT='$BARRIER_PORT' \
  MASTER_IP='$MASTER_IP' \
  MASTER_DB_NAME='$MASTER_DB_NAME' \
  MASTER_DB_USER='$MASTER_DB_USER' \
  MASTER_DB_PASSWORD='$MASTER_DB_PASSWORD' \
  DB_NAME='$DB_NAME' \
  DB_USER='$DB_USER' \
  DB_PASSWORD='$DB_PASSWORD' \
  ALLOWED_HOST='$BOOTH_IP' \
  bash booth_bootstrap.sh
"

echo ""
echo "=== Deployment triggered for booth $BOOTH_NUMBER ($BOOTH_IP) ==="
echo "SSH in to double-check: ssh -p $SSH_PORT $SSH_USER@$BOOTH_IP"

#!/usr/bin/env bash
# Runs ON the booth machine, from inside the extracted mtag_backend/ directory
# (i.e. after the tarball has been copied over and extracted there).
# Not meant to be run by hand normally — deploy_booth.sh (run from the dev
# machine) invokes this over SSH with all the values below set as env vars.
#
# Required env vars: PLAZA_ID, DB_PASSWORD, MASTER_IP, MASTER_DB_NAME
#   PLAZA_ID is the operator-assigned plaza number (Plaza.plaza_id) — it
#   replaced the old PLAZA_CODE, which no longer exists on the model.
# Optional (sensible defaults below): BOOTH_NUMBER, LANE_NUMBER, READER_IP
#   (warns if blank — fine if the reader isn't installed yet), DISPLAY_IP,
#   BARRIER_PORT, DB_NAME, DB_USER, ALLOWED_HOST, GATE_MODE,
#   MASTER_DB_USER, MASTER_DB_PASSWORD
#
# Safe to re-run — venv/DB/pm2 steps are idempotent.

set -euo pipefail

req() {
  local name="$1"
  if [ -z "${!name:-}" ]; then
    echo "ERROR: \$$name is required but not set." >&2
    exit 1
  fi
}
req PLAZA_ID
req DB_PASSWORD
# Without this the booth cannot authenticate to master and mtag-sync dies on
# every cycle — an exit lane then never learns about trips opened elsewhere.
# It used to be allowed to be blank, on the belief that base.py carried a usable
# hardcoded default; base.py now falls back to the BOOTH'S OWN local password,
# which master will always reject. Fail here instead of at 2am on a lane.
req MASTER_DB_PASSWORD

# Catch a stale caller still passing the pre-plaza_id contract, rather than
# writing a non-numeric plaza_id into rfid_config.ini and failing later at
# gate start-up with a much less obvious error.
if ! printf '%s' "$PLAZA_ID" | grep -qE '^[0-9]+$'; then
  echo "ERROR: PLAZA_ID must be an integer plaza number (e.g. 3), got '$PLAZA_ID'." >&2
  echo "  This replaced PLAZA_CODE — pass the plaza's Plaza.plaza_id, not its old code." >&2
  exit 1
fi
req MASTER_IP
req MASTER_DB_NAME

# READER_IP is deliberately NOT in the hard-required list above — a booth's
# reader hardware may not be installed yet when the software/DB side gets
# set up. Left blank, mtag-gate just retries forever with a clear warning
# instead of either crashing here or silently writing "reader_host = " into
# rfid_config.ini (which produced a confusing "TCP:0:9090" connection-refused
# loop the first time this happened).
if [ -z "${READER_IP:-}" ]; then
  echo "WARNING: READER_IP not set — mtag-gate will not be able to reach a" >&2
  echo "  reader until rfid_config.ini's reader_host is set manually and" >&2
  echo "  'pm2 restart mtag-gate' is run. Continuing without it." >&2
fi

BOOTH_NUMBER="${BOOTH_NUMBER:-unnamed}"
LANE_NUMBER="${LANE_NUMBER:-1}"
DISPLAY_IP="${DISPLAY_IP:-192.168.78.72}"
BARRIER_PORT="${BARRIER_PORT:-/dev/ttyUSB0}"
DB_NAME="${DB_NAME:-tag_db}"
DB_USER="${DB_USER:-postgres}"
ALLOWED_HOST="${ALLOWED_HOST:-localhost}"
GATE_MODE="${GATE_MODE:-entry}"
if [ "$GATE_MODE" != "entry" ] && [ "$GATE_MODE" != "exit" ]; then
  echo "ERROR: GATE_MODE must be 'entry' or 'exit', got '$GATE_MODE'." >&2
  echo "  It is written to .env and selects this booth's sync passes —" >&2
  echo "  an exit booth running in entry mode never pulls open trips and" >&2
  echo "  would turn every exiting vehicle away." >&2
  exit 1
fi
MASTER_DB_USER="${MASTER_DB_USER:-$DB_USER}"

echo "=== Booth $BOOTH_NUMBER bootstrap — plaza_id=$PLAZA_ID lane=$LANE_NUMBER ==="

# Refresh the apt package cache once up front — booth machines sitting
# unused since imaging tend to have a stale cache pointing at package
# versions no longer available at the mirror (404s on install otherwise).
#
# Deliberately non-fatal: booth machines accumulate unrelated third-party
# repos (Opera, pgadmin, ...) whose signing keys expire, and a malformed
# hand-added sources.list line is common too. Any one of those makes
# `apt-get update` exit nonzero even though every repo we actually need
# refreshed fine — and under `set -e` that would abort the whole deploy.
# The `apt-get install` calls below are the real gate; they fail loudly if
# a package we need is genuinely unreachable.
echo "--- refreshing apt package lists ---"
if ! sudo apt-get update -qq; then
  echo "!!! apt-get update reported errors (see above) — continuing anyway." >&2
  echo "!!! If a package install fails below, fix this booth's apt sources first." >&2
fi

# ── 1. Python venv ────────────────────────────────────────────────────────
if [ ! -x venv/bin/python3 ] || [ ! -f venv/bin/activate ]; then
  echo "--- (re)creating venv ---"
  rm -rf venv
  # The generic python3-venv package doesn't reliably provide ensurepip for
  # whatever specific python3 minor version is actually installed (confirmed
  # on the master deploy — only the version-pinned package fixed it there).
  # Install both: the exact match, and the generic one as a harmless extra.
  PYVER="$(python3 -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
  echo "--- installing python${PYVER}-venv (system package) ---"
  sudo apt-get install -y "python${PYVER}-venv" python3-venv
  python3 -m venv venv
else
  echo "--- venv already present, reusing it ---"
fi
# shellcheck disable=SC1091
source venv/bin/activate
pip install -q -r requirements.txt

# System-level native library the RFID SDK's HID backend needs at import
# time (even though our readers connect over TCP, not USB/HID — the SDK
# imports this unconditionally). Not pip-installable; `pip install hid`
# only gets the Python binding, not the underlying C library.
echo "--- installing libhidapi (system package, not pip-installable) ---"
sudo apt-get install -y libhidapi-hidraw0 libhidapi-libusb0 >/dev/null 2>&1 || true

# ── 1b. Vendored RFID SDK (com.rfid) ──────────────────────────────────────
# Not on PyPI (proprietary vendor package, was originally pip-installed from
# a local .whl) — vendored directly into vendor/rfid_sdk/com/ from the exact
# version (1.1) already approved and working on a real booth. Copied into
# site-packages on every run so it's always present regardless of whether
# the venv above was just created or already existed.
SITE_PACKAGES="$(python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
echo "--- installing vendored RFID SDK into $SITE_PACKAGES ---"
rm -rf "${SITE_PACKAGES:?}/com"
cp -a vendor/rfid_sdk/com "$SITE_PACKAGES/com"

# ── 2. .env ───────────────────────────────────────────────────────────────
echo "--- writing .env ---"
cp .env.booth.example .env
sed -i "s/^DJANGO_SETTINGS_MODULE=.*/DJANGO_SETTINGS_MODULE=config.settings.lan/" .env
sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(50))')|" .env
sed -i "s/^ALLOWED_HOSTS=.*/ALLOWED_HOSTS=localhost,127.0.0.1,${ALLOWED_HOST}/" .env
# GATE_MODE drives which sync passes mtag-sync runs (entry=push+ref/closed,
# exit=+open trips). Validated as entry|exit at the top of this script.
sed -i "s/^GATE_MODE=.*/GATE_MODE=${GATE_MODE}/" .env
sed -i "s/^DB_NAME=.*/DB_NAME=${DB_NAME}/" .env
sed -i "s/^DB_USER=.*/DB_USER=${DB_USER}/" .env
sed -i "s/^DB_PASSWORD=.*/DB_PASSWORD=${DB_PASSWORD}/" .env
sed -i "s/^MASTER_DB_HOST=.*/MASTER_DB_HOST=${MASTER_IP}/" .env
sed -i "s/^MASTER_DB_NAME=.*/MASTER_DB_NAME=${MASTER_DB_NAME}/" .env
sed -i "s/^MASTER_DB_USER=.*/MASTER_DB_USER=${MASTER_DB_USER}/" .env
sed -i "s/^MASTER_DB_PASSWORD=.*/MASTER_DB_PASSWORD=${MASTER_DB_PASSWORD}/" .env

# ── 3. rfid_config.ini ────────────────────────────────────────────────────
echo "--- writing rfid_config.ini ---"
cp rfid_config.ini.example rfid_config.ini
sed -i "s/^mode = .*/mode = ${GATE_MODE}/" rfid_config.ini
sed -i "s/^plaza_id = .*/plaza_id = ${PLAZA_ID}/" rfid_config.ini
sed -i "s/^lane_number = .*/lane_number = ${LANE_NUMBER}/" rfid_config.ini
sed -i "s/^reader_host = .*/reader_host = ${READER_IP:-READER-NOT-CONFIGURED}/" rfid_config.ini
sed -i "s|^port = .*|port = ${BARRIER_PORT}|" rfid_config.ini
sed -i "s/^display_ip = .*/display_ip = ${DISPLAY_IP}/" rfid_config.ini

# ── 4. Local Postgres ─────────────────────────────────────────────────────
echo "--- configuring local Postgres ---"
if [ "$DB_USER" = "postgres" ]; then
  sudo -u postgres psql -c "ALTER USER postgres WITH PASSWORD '${DB_PASSWORD}';" >/dev/null
else
  sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';" >/dev/null
fi
sudo -u postgres psql -lqt | cut -d '|' -f1 | grep -qw "${DB_NAME}" || \
  sudo -u postgres createdb -O "${DB_USER}" "${DB_NAME}"

# ── 5. Migrate ────────────────────────────────────────────────────────────
echo "--- running migrations ---"
python manage.py migrate

# ── 5b. Clear stale pre-seeded data (cloned disk image artifact) ──────────
# Some booth machines are provisioned from a shared disk image whose local
# DB already has plazas/lanes/rates/tags seeded with different UUIDs than
# master's canonical rows (same root cause hit on two separate booths so
# far) — causes the sync agent's very first pull to fail permanently with
# "duplicate key ... plazas_code_key". These tables are master-owned/
# full-refresh per pull_service.py, so it's always correct for them to be
# empty and let the sync agent repopulate them from master — EXCEPT once
# real trips exist locally (toll_trips FKs to plazas, so clearing would
# cascade-delete real activity). Only touch it when toll_trips is empty.
# (The duplicate-key error is now on plazas_plaza_id_key rather than the old
# plazas_code_key, since plaza_id replaced code as the unique column.)
echo "--- checking for stale pre-seeded data (cloned-image artifact) ---"
TRIP_COUNT="$(sudo -u postgres psql -tAc 'SELECT COUNT(*) FROM toll_trips' "${DB_NAME}" 2>/dev/null || echo 0)"
if [ "${TRIP_COUNT:-0}" = "0" ]; then
  echo "--- no real trips yet — clearing plazas/toll_lanes/toll_rates/tags so the sync agent pulls master's canonical rows cleanly ---"
  sudo -u postgres psql -c "TRUNCATE plazas, toll_lanes, toll_rates, tags CASCADE;" "${DB_NAME}" >/dev/null
else
  echo "--- ${TRIP_COUNT} existing trip(s) found — NOT touching plaza/rate data (this booth has real activity) ---"
fi

# ── 6. PM2 ────────────────────────────────────────────────────────────────
if ! command -v pm2 >/dev/null 2>&1; then
  echo "--- pm2 not found — installing Node.js + PM2 (not present on this booth's base image) ---"
  sudo apt-get install -y nodejs npm
  sudo npm install -g pm2
fi

echo "--- starting PM2 ---"
# mtag-sync included: the sync agent no longer runs inside mtag-web, it is its
# own process now. Deleting it too means re-running this script on a booth
# provisioned before that split cleanly replaces the old process set.
pm2 delete mtag-web mtag-gate mtag-sync >/dev/null 2>&1 || true
pm2 start ecosystem.config.js
pm2 save

echo ""
echo "=== Bootstrap complete for booth $BOOTH_NUMBER (mode=$GATE_MODE) ==="
echo "Verify with:"
echo "  pm2 status                        # mtag-web, mtag-gate, mtag-sync all online"
echo "  pm2 logs mtag-sync   # look for: [sync] Agent started — mode=${GATE_MODE}"
echo "  pm2 logs mtag-gate   # look for: [reader] Connected to TCP:${READER_IP}:..."
echo "  python manage.py sync_service --once    # one cycle, verbose"
echo "  python manage.py trip_sync             # DRIFT must be 0"
echo ""
echo "If PM2 has never run on this machine before, also run the command"
echo "below ONCE (pm2 startup only prints it, doesn't run it) so it survives reboot:"
pm2 startup 2>&1 | grep "sudo env" || true

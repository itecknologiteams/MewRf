#!/usr/bin/env bash
# Runs ON the booth. Installs/updates the code that deploy_booths.sh just
# extracted, verifies the booth can reach master's database, and (re)starts PM2.
#
# STRICT ONLINE-ONLY: booths have no local Postgres. .env points DB_* at master,
# so this script never creates, migrates or seeds a database — master owns all of
# it. That also means a booth is useless without the link to master, by design.
#
# Unlike booth_bootstrap.sh this NEVER writes over an existing .env or
# rfid_config.ini — a redeploy must not silently reset a booth's reader IP,
# antenna power or RSSI tuning. Missing config is created from the examples and
# the run stops so it can be filled in over SSH.
#
# Exit codes are meaningful; deploy_booths.sh reports them per booth:
#   0  deployed and running
#   2  config missing or still pointing at a local database — fix, then re-run
#   4  Node/PM2 unavailable, so the services could not be started
#   5  Python dependencies could not be installed
#   7  master's database is unreachable from this booth
#   1  anything else

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

echo "=== booth update on $(hostname) ==="

# ── 1. venv + Python deps ────────────────────────────────────────────────────
WHEELHOUSE="$PWD/wheelhouse"
have_wheels() { ls "$WHEELHOUSE"/*.whl >/dev/null 2>&1; }
have_wheels && echo "--- wheelhouse present ($(ls "$WHEELHOUSE"/*.whl | wc -l) wheels) — offline install available ---"

if [ ! -x venv/bin/python3 ] || [ ! -f venv/bin/activate ]; then
  echo "--- creating venv ---"
  rm -rf venv
  # Try the venv module BEFORE touching apt. apt is the fragile part — most
  # booths have no DNS, so an unconditional `apt-get install` killed the deploy
  # even on booths where `python3 -m venv` works fine (one was seen merely
  # *upgrading* an already-installed python3.12-venv when it died).
  if ! python3 -m venv venv 2>/dev/null; then
    rm -rf venv
    # "ensurepip is not available" is printed BY the venv module, so the module
    # itself is fine — only python3-venv's ensurepip is absent. That is
    # recoverable entirely offline: build the environment without pip, then run
    # pip straight out of its own wheel to populate it. No apt, no PyPI.
    if have_wheels && python3 -m venv --without-pip venv 2>/dev/null; then
      echo "--- no ensurepip — bootstrapping pip from the wheelhouse ---"
      PIP_WHL="$(ls "$WHEELHOUSE"/pip-*.whl 2>/dev/null | head -1)"
      if [ -z "$PIP_WHL" ] || ! venv/bin/python "$PIP_WHL/pip" install -q \
           --no-index --find-links="$WHEELHOUSE" pip setuptools wheel; then
        echo "!!! Could not bootstrap pip from the wheelhouse." >&2
        exit 5
      fi
    else
      echo "--- venv module unavailable — trying apt ---"
      rm -rf venv
      # The generic python3-venv package does not reliably carry ensurepip for
      # the exact python3 minor version installed; ask for the pinned one too.
      PYVER="$(python3 -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
      sudo apt-get install -y "python${PYVER}-venv" python3-venv || \
        echo "!!! apt failed (no network?) — attempting venv creation regardless" >&2
      rm -rf venv
      if ! python3 -m venv venv; then
        echo "!!! Could not create a virtualenv on this booth." >&2
        echo "!!! No ensurepip, no apt, and no wheelhouse to bootstrap from." >&2
        exit 5
      fi
    fi
  fi
else
  echo "--- reusing existing venv ---"
fi
# shellcheck disable=SC1091
source venv/bin/activate

echo "--- installing Python dependencies ---"
# Offline first. These booths cannot reach PyPI, and --no-index also makes the
# install deterministic on the ones that can.
if have_wheels; then
  if ! pip install -q --no-index --find-links="$WHEELHOUSE" -r requirements.txt; then
    echo "!!! Offline install from the wheelhouse failed." >&2
    echo "!!! The wheels may not match this booth's Python. Check BOOTH_PYVER in" >&2
    echo "!!! deploy_booths.sh against: $(python3 -V 2>&1)" >&2
    exit 5
  fi
elif ! pip install -q -r requirements.txt; then
  echo "!!! pip could not install the dependencies and there is no wheelhouse." >&2
  echo "!!! Re-run deploy_booths.sh so it builds and ships one." >&2
  exit 5
fi

# System library the RFID SDK imports unconditionally, even for TCP readers.
# Not pip-installable. Best effort: a booth that already has it must not fail
# here just because its apt sources are broken.
sudo apt-get install -y libhidapi-hidraw0 libhidapi-libusb0 >/dev/null 2>&1 || \
  echo "!!! libhidapi install skipped (apt failed) — fine if already present"

# ── 2. Vendored RFID SDK ─────────────────────────────────────────────────────
# Proprietary, not on PyPI. Recopied every run so it survives a venv rebuild.
SITE_PACKAGES="$(python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
echo "--- installing vendored RFID SDK ---"
rm -rf "${SITE_PACKAGES:?}/com"
cp -a vendor/rfid_sdk/com "$SITE_PACKAGES/com"

# ── 3. Config — create if absent, never overwrite ────────────────────────────
NEEDS_CONFIG=0
if [ ! -f .env ]; then
  cp .env.booth.example .env
  echo "!!! .env was missing — created from .env.booth.example"
  NEEDS_CONFIG=1
fi
if [ ! -f rfid_config.ini ]; then
  cp rfid_config.ini.example rfid_config.ini
  echo "!!! rfid_config.ini was missing — created from rfid_config.ini.example"
  NEEDS_CONFIG=1
fi
if [ "$NEEDS_CONFIG" = "1" ]; then
  echo ""
  echo "=== CONFIGURE THIS BOOTH, THEN RE-RUN ==="
  echo "  ssh $(whoami)@$(hostname -I | awk '{print $1}')"
  echo "  cd ~/mtag_backend"
  echo "  nano .env              # SECRET_KEY, DB_*, MASTER_DB_*, GATE_MODE, ALLOWED_HOSTS"
  echo "  nano rfid_config.ini   # mode, plaza_id, lane_number, reader_host, display_ip, barrier port"
  echo ""
  echo "Nothing was migrated or started — the database credentials are not known yet."
  exit 2
fi

# ── 4. Master database connectivity ──────────────────────────────────────────
# This deployment is strict online-only: a booth has NO local Postgres. Its .env
# points DB_* straight at master, so there is nothing here to create, migrate or
# seed — master owns the schema and the data.
#
# What used to live here has been deliberately removed, not just disabled:
#   * createdb / CREATE ROLE — there is no local server to create them on.
#   * manage.py migrate — 21 booths migrating master's database concurrently is
#     a race with no upside. master_bootstrap.sh is the only thing that migrates.
#   * TRUNCATE plazas, toll_lanes, toll_rates, tags — this let a booth's first
#     sync refill reference data from master. It ran over the LOCAL socket, so
#     it could not reach master, but with no local database it is now either a
#     no-op or an error. Gone either way.
#   * the migration-history check — master's schema, master's problem.
#
# All that is left is proving the booth can actually reach master, because with
# no local database that connection IS the booth.

# `|| true` matters: a key absent from .env makes grep exit 1, which under
# `set -e` would kill the script inside the command substitutions below, before
# any default or error message could apply.
get_env() { grep -aE "^$1=" .env 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"'"'"'' || true ; }

# manage.py falls back to config.settings.local when the shell does not export
# this. .env sets it, but .env is only read from inside the settings module —
# far too late to choose which one loads. Without this the check below would run
# under dev settings, where master_pg is aliased to the local database.
export DJANGO_SETTINGS_MODULE="$(get_env DJANGO_SETTINGS_MODULE)"
: "${DJANGO_SETTINGS_MODULE:=config.settings.lan}"
export DJANGO_SETTINGS_MODULE
echo "--- settings module: $DJANGO_SETTINGS_MODULE ---"

DB_HOST_CFG="$(get_env DB_HOST)"
DB_NAME_CFG="$(get_env DB_NAME)"
DB_USER_CFG="$(get_env DB_USER)"
: "${DB_NAME_CFG:?DB_NAME not set in .env}"
: "${DB_USER_CFG:?DB_USER not set in .env}"

if [ -z "$DB_HOST_CFG" ] || [ "$DB_HOST_CFG" = "localhost" ] || [ "$DB_HOST_CFG" = "127.0.0.1" ]; then
  echo "!!! DB_HOST is '${DB_HOST_CFG:-<empty>}' — this booth is still configured for a" >&2
  echo "!!! local database. Online-only booths must point DB_HOST at master." >&2
  echo "!!! Edit .env over SSH (DB_HOST/DB_NAME/DB_USER/DB_PASSWORD = master's)." >&2
  exit 2
fi

echo "--- checking master database $DB_USER_CFG@$DB_HOST_CFG/$DB_NAME_CFG ---"
if ! python - <<'PYCHK'
import sys, django
django.setup()
from django.db import connection
try:
    with connection.cursor() as c:
        c.execute("SELECT COUNT(*) FROM plazas")
        print(f"    reachable — {c.fetchone()[0]} plaza(s) visible")
except Exception as exc:
    print(f"    UNREACHABLE: {exc}", file=sys.stderr)
    sys.exit(1)
PYCHK
then
  echo "!!! Cannot reach master's database from this booth." >&2
  echo "!!! With no local DB the gate cannot work at all, so nothing was started." >&2
  echo "!!! Check DB_* in .env, master's pg_hba.conf/listen_addresses, and the link." >&2
  exit 7
fi

# ── 7. PM2 ───────────────────────────────────────────────────────────────────
# Not every booth image ships PM2, or even Node. The ones that don't tend to be
# the same ones with broken apt sources (booth 05 had bad GPG keys and a
# malformed Ubuntu line), so install defensively: report something actionable
# instead of letting `set -e` abort on a raw apt error, and confirm pm2 actually
# runs afterwards rather than assuming the install worked.
ensure_pm2() {
  if command -v pm2 >/dev/null 2>&1; then
    echo "--- pm2 present ($(pm2 --version 2>/dev/null || echo 'version unknown')) ---"
    return 0
  fi

  echo "--- pm2 not found — installing ---"
  if ! command -v npm >/dev/null 2>&1; then
    echo "--- installing Node.js + npm ---"
    if ! sudo apt-get install -y nodejs npm; then
      echo "!!! apt could not install nodejs/npm on this booth." >&2
      echo "!!! Its apt sources are most likely broken — fix those, or install" >&2
      echo "!!! Node by hand, then re-run the deploy." >&2
      return 1
    fi
  fi

  echo "--- installing pm2 globally ---"
  if ! sudo npm install -g pm2; then
    echo "!!! npm could not install pm2 (no registry access from this booth?)." >&2
    return 1
  fi

  # A just-installed binary is not in this shell's command-lookup cache, and
  # npm's global bin directory is not always on a non-login shell's PATH.
  hash -r 2>/dev/null || true
  if ! command -v pm2 >/dev/null 2>&1; then
    NPM_PREFIX="$(npm config get prefix 2>/dev/null || true)"
    for p in /usr/local/bin /usr/bin "${NPM_PREFIX:-/usr/local}/bin"; do
      if [ -x "$p/pm2" ]; then export PATH="$p:$PATH"; break; fi
    done
  fi
  command -v pm2 >/dev/null 2>&1
}

if ! ensure_pm2; then
  echo "!!! PM2 unavailable — this booth's services were NOT started." >&2
  echo "!!! Everything else (code, dependencies, database, migrations) is in place," >&2
  echo "!!! so re-running the deploy once Node works will finish the job." >&2
  exit 4
fi

echo "--- (re)starting PM2 ---"
# mtag-sync is deliberately NOT started. It replicates between a booth's local
# database and master; with DB_* pointing at master both ends are the same
# server, so every pass would copy master onto itself — advancing watermarks,
# resyncing sequences and re-pushing trips for no reason. The delete below also
# stops it on booths provisioned before this change.
pm2 delete mtag-web mtag-gate mtag-sync >/dev/null 2>&1 || true
pm2 start ecosystem.config.js --only mtag-web,mtag-gate
pm2 save

# Survive a power cut. `pm2 startup` only PRINTS the systemd command, it does not
# run it — so without this a booth reboots into no gate process at all, and the
# barrier simply never opens until someone notices and SSHes in.
echo "--- enabling PM2 on boot ---"
STARTUP_CMD="$(pm2 startup systemd -u "$USER" --hp "$HOME" 2>/dev/null | grep -E '^sudo ' | tail -1 || true)"
if [ -n "$STARTUP_CMD" ]; then
  if eval "$STARTUP_CMD" >/dev/null 2>&1; then
    echo "    pm2 will restart the services on boot"
    pm2 save >/dev/null 2>&1 || true
  else
    echo "!!! could not enable pm2 on boot — run 'pm2 startup' here by hand" >&2
  fi
else
  echo "    pm2 boot service already configured"
fi

echo ""
pm2 status
echo "=== booth update complete ==="

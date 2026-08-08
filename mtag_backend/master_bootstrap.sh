#!/usr/bin/env bash
# Runs ON the master server, from inside the extracted mtag_backend/ directory.
# Not meant to be run by hand normally — deploy_master.sh (run from the dev
# machine) invokes this over SSH with the values below set as env vars.
#
# Required env vars: DB_PASSWORD, ALLOWED_HOST
# Optional (sensible defaults below): DB_NAME, DB_USER, CORS_ORIGINS
#
# How this differs from booth_bootstrap.sh — read before editing:
#   * NO rfid_config.ini and no mtag-gate process. Master has no reader.
#   * NEVER truncates plazas/toll_lanes/toll_rates/tags. Master IS the source of
#     truth for those; the booth script clears them precisely so the sync agent
#     can refill them FROM master. Doing that here would wipe the network.
#   * No mtag-sync process. Master is the sync SOURCE, so it never syncs — that
#     is enforced by ecosystem.master.config.js defining only mtag-master, NOT
#     by any setting. ANPR_GATE_ENABLED=False only stops the ANPR gate.
#   * Runs gunicorn via ecosystem.master.config.js, not `manage.py runserver`.
#
# Safe to re-run — venv/DB/pm2 steps are idempotent, and an existing SECRET_KEY
# is preserved rather than rotated (rotating it logs every operator out).

set -euo pipefail

req() {
  local name="$1"
  if [ -z "${!name:-}" ]; then
    echo "ERROR: \$$name is required but not set." >&2
    exit 1
  fi
}
req DB_PASSWORD
req ALLOWED_HOST

DB_NAME="${DB_NAME:-master_tag_db}"
DB_USER="${DB_USER:-postgres}"
CORS_ORIGINS="${CORS_ORIGINS:-}"

echo "=== Master bootstrap — db=$DB_NAME host=$ALLOWED_HOST ==="

# config.settings.lan does CORS_ALLOWED_ORIGINS = env.list(..., default=[]),
# which OVERRIDES the list in base.py. An empty value therefore allows NO
# origin at all: the browser's preflight still returns 200, but the response
# carries no Access-Control-Allow-Origin, so every real request is silently
# blocked and the portal just appears dead. Warn loudly rather than ship that.
if [ -z "${CORS_ORIGINS:-}" ]; then
  echo "!!! WARNING: CORS_ORIGINS is empty." >&2
  echo "!!!   The admin portal will be blocked by CORS — preflights return 200" >&2
  echo "!!!   but every POST/GET from the browser is refused." >&2
  echo "!!!   Set CORS_ORIGINS in deploy_master.sh to the portal's origin(s)," >&2
  echo "!!!   e.g. http://${ALLOWED_HOST}:5173 — comma-separated, no spaces." >&2
fi

# Non-fatal for the same reason as the booth script: unrelated third-party
# repos with expired keys must not abort a deployment. The installs below are
# the real gate.
echo "--- refreshing apt package lists ---"
if ! sudo apt-get update -qq; then
  echo "!!! apt-get update reported errors (see above) — continuing anyway." >&2
fi

# ── 1. Python venv ────────────────────────────────────────────────────────
if [ ! -x venv/bin/python3 ] || [ ! -f venv/bin/activate ]; then
  echo "--- (re)creating venv ---"
  rm -rf venv
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

# ── 2. .env ───────────────────────────────────────────────────────────────
# Generated inline rather than copied from a template: master's values are few
# and specific, and an existing SECRET_KEY must survive a re-deploy.
echo "--- writing .env ---"
if [ -f .env ] && grep -q '^SECRET_KEY=..*' .env; then
  SECRET_KEY="$(grep '^SECRET_KEY=' .env | head -1 | cut -d= -f2-)"
  echo "    (reusing existing SECRET_KEY)"
else
  SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(50))')"
  echo "    (generated a new SECRET_KEY)"
fi

cat > .env <<ENV
DJANGO_SETTINGS_MODULE=config.settings.lan
SECRET_KEY=${SECRET_KEY}
ALLOWED_HOSTS=localhost,127.0.0.1,${ALLOWED_HOST}
CORS_ALLOWED_ORIGINS=${CORS_ORIGINS}

# Master's own database. DB_* and MASTER_DB_* deliberately point at the SAME
# local server: master is its own authority, and services.py's dual-write opens
# a 'master_pg' connection even when running here.
DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASSWORD}
DB_HOST=localhost
DB_PORT=5432
DB_FALLBACK_HOST=

MASTER_DB_HOST=localhost
MASTER_DB_NAME=${DB_NAME}
MASTER_DB_USER=${DB_USER}
MASTER_DB_PASSWORD=${DB_PASSWORD}

# Master has no RFID hardware, so the ANPR gate must not auto-start here.
# NOTE: this does NOT control syncing. Master simply does not run the mtag-sync
# process (see ecosystem.master.config.js) — that is what keeps it from syncing
# against itself.
ANPR_GATE_ENABLED=False

JAZZCASH_MERCHANT_ID=
JAZZCASH_PASSWORD=
JAZZCASH_INTEGRITY_SALT=
JAZZCASH_RETURN_URL=
ENV

# ── 3. Local Postgres ─────────────────────────────────────────────────────
echo "--- configuring Postgres ---"
if [ "$DB_USER" = "postgres" ]; then
  sudo -u postgres psql -c "ALTER USER postgres WITH PASSWORD '${DB_PASSWORD}';" >/dev/null
else
  sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';" >/dev/null
fi
sudo -u postgres psql -lqt | cut -d '|' -f1 | grep -qw "${DB_NAME}" || \
  sudo -u postgres createdb -O "${DB_USER}" "${DB_NAME}"

# Booths connect to this Postgres over the LAN for the synchronous dual-write,
# so it must listen on more than the loopback interface. Warn rather than edit
# postgresql.conf/pg_hba.conf automatically — that is a security decision.
LISTEN="$(sudo -u postgres psql -tAc 'SHOW listen_addresses' 2>/dev/null || echo '?')"
if [ "$LISTEN" = "localhost" ] || [ "$LISTEN" = "127.0.0.1" ]; then
  echo "!!! WARNING: Postgres listen_addresses='${LISTEN}' — booths CANNOT reach it." >&2
  echo "!!!   Set listen_addresses='*' in postgresql.conf and add a pg_hba.conf" >&2
  echo "!!!   line for the booth subnet, then restart postgresql." >&2
  echo "!!!   Without this every booth entry/exit fails (online-only system)." >&2
fi

# ── 4. Migrate ────────────────────────────────────────────────────────────
# Deliberately NOT followed by any TRUNCATE. Master owns plazas/lanes/rates/tags.
echo "--- running migrations ---"
python manage.py migrate

echo "--- collecting static files (admin + DRF UI) ---"
python manage.py collectstatic --noinput >/dev/null

# ── 5. Plaza sanity check ─────────────────────────────────────────────────
# Booths resolve their gate from Plaza.plaza_id, so master must actually have
# those rows before any booth is useful. Report, don't auto-seed: master may
# hold real data and seed_data.py is a dev convenience.
PLAZA_COUNT="$(sudo -u postgres psql -tAc 'SELECT COUNT(*) FROM plazas' "${DB_NAME}" 2>/dev/null || echo 0)"
echo "--- plazas on master: ${PLAZA_COUNT} ---"
if [ "${PLAZA_COUNT:-0}" = "0" ]; then
  echo "!!! No plazas on master. Booths resolve their lane by Plaza.plaza_id and" >&2
  echo "!!!   will refuse to start until these exist. Create them via the admin" >&2
  echo "!!!   portal, or run 'python manage.py seed_data' for the Malir set." >&2
else
  echo "--- plaza_id values booths can be pointed at: ---"
  sudo -u postgres psql -c \
    'SELECT plaza_id, name, is_active FROM plazas ORDER BY plaza_id;' "${DB_NAME}"
fi

# ── 6. PM2 ────────────────────────────────────────────────────────────────
if ! command -v pm2 >/dev/null 2>&1; then
  echo "--- pm2 not found — installing Node.js + PM2 ---"
  sudo apt-get install -y nodejs npm
  sudo npm install -g pm2
fi

echo "--- starting PM2 (gunicorn) ---"
pm2 delete mtag-master >/dev/null 2>&1 || true
pm2 start ecosystem.master.config.js
pm2 save

echo ""
echo "=== Master bootstrap complete ==="
pm2 status
echo ""
echo "Verify:  pm2 logs mtag-master --lines 50"
echo "API:     curl -s http://${ALLOWED_HOST}:8000/api/v1/ | head"

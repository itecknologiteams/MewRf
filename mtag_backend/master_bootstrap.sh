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
#     is enforced by ecosystem.master.config.js never defining mtag-sync or
#     mtag-gate, NOT by any setting. ANPR_GATE_ENABLED=False only stops the ANPR
#     gate. Master does run a second app, mtag-deploy: the worker that pushes
#     code to booths when an operator asks for it in the portal.
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
DB_USER="${DB_USER:-rfid}"        # application role, NOT a superuser
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
# This file is rewritten wholesale, so anything set by hand on master and not
# named here is lost. Carry the credentials forward explicitly: a redeploy that
# silently blanked JAZZCASH_* would take payments down with no error anywhere,
# and the same now applies to the FCM keys.
# `|| true` — a missing key makes grep exit 1, which under `set -e` would abort
# the deploy inside the command substitution.
old_env() { [ -f .env ] && { grep -aE "^$1=" .env | tail -1 | cut -d= -f2- || true; } || true; }
OLD_JAZZCASH_MERCHANT_ID="$(old_env JAZZCASH_MERCHANT_ID)"
OLD_JAZZCASH_PASSWORD="$(old_env JAZZCASH_PASSWORD)"
OLD_JAZZCASH_INTEGRITY_SALT="$(old_env JAZZCASH_INTEGRITY_SALT)"
OLD_JAZZCASH_RETURN_URL="$(old_env JAZZCASH_RETURN_URL)"
OLD_FCM_PROJECT_ID="$(old_env FCM_PROJECT_ID)"
OLD_FCM_CREDENTIALS_FILE="$(old_env FCM_CREDENTIALS_FILE)"
OLD_USER_SELF_REGISTRATION_ENABLED="$(old_env USER_SELF_REGISTRATION_ENABLED)"
: "${OLD_USER_SELF_REGISTRATION_ENABLED:=False}"
OLD_OTP_PUSH_SUPPRESSES_SMS="$(old_env OTP_PUSH_SUPPRESSES_SMS)"
: "${OLD_OTP_PUSH_SUPPRESSES_SMS:=False}"
# The dev OTP push and the list of test numbers it is confined to. Carried forward
# TOGETHER and never one without the other: config.settings.lan refuses to boot with
# the mode on and the list empty, so a redeploy that preserved only the flag would
# write an .env that crash-loops gunicorn.
OLD_OTP_PUSH_TO_REQUESTING_DEVICE="$(old_env OTP_PUSH_TO_REQUESTING_DEVICE)"
: "${OLD_OTP_PUSH_TO_REQUESTING_DEVICE:=False}"
OLD_OTP_DEV_PUSH_PHONES="$(old_env OTP_DEV_PUSH_PHONES)"
# Credentials mtag-deploy uses to SSH into a booth. Carried forward for the same
# reason as the keys above: a redeploy that blanked them would leave every
# portal-triggered booth update failing on authentication.
OLD_BOOTH_SSH_USER="$(old_env BOOTH_SSH_USER)"
: "${OLD_BOOTH_SSH_USER:=${BOOTH_SSH_USER:-iteck}}"
OLD_BOOTH_SSH_PASSWORD="$(old_env BOOTH_SSH_PASSWORD)"
: "${OLD_BOOTH_SSH_PASSWORD:=${BOOTH_SSH_PASSWORD:-}}"

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
# ALLOWED_HOST may be a comma-separated list (public,LAN) — it is spliced in as-is.
# Master answers on both interfaces and a missing entry makes Django 400 every
# request from that address before any view or CORS rule runs.
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

# ── Booth code updates (portal → mtag-deploy → booth) ───────────────────────
# The account the deploy worker SSHes into a booth as, and its password. Same
# shared credentials deploy_booths.sh uses. Leave the password empty to use SSH
# keys instead — then master's key must be in each booth's authorized_keys.
BOOTH_SSH_USER=${OLD_BOOTH_SSH_USER}
BOOTH_SSH_PASSWORD=${OLD_BOOTH_SSH_PASSWORD}

JAZZCASH_MERCHANT_ID=${OLD_JAZZCASH_MERCHANT_ID}
JAZZCASH_PASSWORD=${OLD_JAZZCASH_PASSWORD}
JAZZCASH_INTEGRITY_SALT=${OLD_JAZZCASH_INTEGRITY_SALT}
JAZZCASH_RETURN_URL=${OLD_JAZZCASH_RETURN_URL}

# Push notifications (FCM HTTP v1). Blank on a LAN-only deployment, where every
# send is skipped and /notifications/status/ reports push_available=false.
# FCM_CREDENTIALS_FILE is a PATH to the service-account JSON, never the key.
FCM_PROJECT_ID=${OLD_FCM_PROJECT_ID}
FCM_CREDENTIALS_FILE=${OLD_FCM_CREDENTIALS_FILE}

# Anonymous self-registration. Off unless it was already on — that endpoint has
# no phone verification, so enabling it lets anyone create users against numbers
# they do not own.
USER_SELF_REGISTRATION_ENABLED=${OLD_USER_SELF_REGISTRATION_ENABLED}

# ── OTP delivery ─────────────────────────────────────────────────────────────
# Listed here so a deploy PRESERVES them. This file is rewritten wholesale on every
# run, and only keys named in this template survive — a value appended by hand is
# silently dropped on the next deploy, which is exactly how dev OTP push stopped
# working after appearing to have been configured correctly.
#
# TESTING ONLY, and the two lines below are a PAIR. The mode delivers the code to
# whatever device asked for it; OTP_DEV_PUSH_PHONES is what stops that being a
# one-step takeover of every account on the system, by confining it to the handsets
# actually under test — any other number falls back to SMS as if the mode were off.
#
# Master runs config.settings.lan, which refuses to boot with the mode on and the
# list empty (config/settings/hardening.py). So: set both, or neither. Master is also
# reachable from the internet as api.maliroperations.com, not just from the plaza
# LAN, so every number on this list is exposed to anyone who knows it — keep the list
# to the handsets being tested and empty it when testing ends.
#
# Leave the mode off and the console SMS backend writes every code to the log instead:
#     pm2 logs mtag-master | grep SMS:console
OTP_PUSH_TO_REQUESTING_DEVICE=${OLD_OTP_PUSH_TO_REQUESTING_DEVICE}
OTP_DEV_PUSH_PHONES=${OLD_OTP_DEV_PUSH_PHONES}

# Skip the SMS when a push demonstrably reached a device already bound to the
# account. Off by default: a bound device may be one the holder no longer carries,
# and there is no password reset without an OTP.
OTP_PUSH_SUPPRESSES_SMS=${OLD_OTP_PUSH_SUPPRESSES_SMS}
ENV

# ── 3. Local Postgres ─────────────────────────────────────────────────────
echo "--- configuring Postgres ---"

# Two DISTINCT roles, deliberately not the same one:
#
#   DB_ADMIN_USER  a superuser (postgres) used only for cluster-level DDL here:
#                  creating the app role and the database. Never written to .env.
#   DB_USER        the application role (RFID). Owns master_tag_db, and is what
#                  Django on master and every booth actually connects as.
#
# Keeping them apart means booths hold credentials that cannot create or drop
# databases, cannot touch other databases, and cannot alter roles — while the
# superuser password never leaves this machine.
DB_ADMIN_USER="${DB_ADMIN_USER:-postgres}"

# Role names are CASE-SENSITIVE once quoted, and every identifier below is
# quoted — so DB_USER is used verbatim. This deployment's role is lower-case
# `rfid`, which is exactly what an unquoted `CREATE USER RFID` produces, since
# Postgres folds unquoted identifiers to lower case. Passing "RFID" here would
# look for a different role and fail with `role "RFID" does not exist`.
# Reaching Postgres as a superuser is done two ways, in this order, because
# masters differ in how pg_hba.conf is set up:
#
#   1. sudo -u postgres psql   works when pg_hba grants the postgres OS user
#                              peer/trust on the local socket.
#   2. TCP with a password     needed when pg_hba requires md5/scram even
#                              locally — which is how THIS master is configured:
#                              `sudo -u postgres psql` there prompts
#                              "Password for user postgres:" and hangs.
#
# -w on every attempt is what makes this safe to probe: psql then fails instead
# of stopping to prompt, so detection is deterministic and a wrong guess cannot
# leave the deploy waiting on a terminal.
ADMIN_MODE=""
if sudo -n -u "$DB_ADMIN_USER" psql -w -tAc 'SELECT 1' >/dev/null 2>&1; then
  ADMIN_MODE="peer"
elif [ -n "${DB_ADMIN_PASSWORD:-}" ] && \
     PGPASSWORD="$DB_ADMIN_PASSWORD" psql -w -h localhost -U "$DB_ADMIN_USER" \
       -d postgres -tAc 'SELECT 1' >/dev/null 2>&1; then
  ADMIN_MODE="tcp"
fi

psql_super() {
  case "$ADMIN_MODE" in
    peer) sudo -n -u "$DB_ADMIN_USER" psql -w -v ON_ERROR_STOP=1 "$@" ;;
    tcp)  PGPASSWORD="$DB_ADMIN_PASSWORD" psql -w -h localhost \
            -U "$DB_ADMIN_USER" -v ON_ERROR_STOP=1 "$@" ;;
  esac
}

if [ -z "$ADMIN_MODE" ]; then
  echo "!!! Cannot reach Postgres as the $DB_ADMIN_USER superuser." >&2
  echo "!!!   Tried: sudo -u $DB_ADMIN_USER psql (peer/trust), and a TCP" >&2
  echo "!!!   connection with DB_ADMIN_PASSWORD${DB_ADMIN_PASSWORD:+ (which was set)}." >&2
  echo "!!!" >&2
  echo "!!!   Superuser access is needed to create the ${DB_USER} role and" >&2
  echo "!!!   ${DB_NAME}. Either set DB_ADMIN_PASSWORD in deploy_master.sh to" >&2
  echo "!!!   the $DB_ADMIN_USER password, or grant the $DB_ADMIN_USER OS user" >&2
  echo "!!!   peer access in pg_hba.conf." >&2
  exit 1
fi
echo "    superuser access via ${ADMIN_MODE}"

# Create the app role if absent; only set its password when it cannot already
# authenticate. Rotating it unprompted would break every booth carrying the old
# one, and booths discover that with a vehicle already at the barrier.
if psql_super -tAc "SELECT 1 FROM pg_roles WHERE rolname = '${DB_USER}'" | grep -q 1; then
  if PGPASSWORD="$DB_PASSWORD" psql -h localhost -U "$DB_USER" -d postgres \
       -tAc 'SELECT 1' >/dev/null 2>&1; then
    echo "    role ${DB_USER} exists and its password is valid — unchanged"
  else
    echo "!!! Role ${DB_USER} exists but cannot authenticate with DB_PASSWORD." >&2
    echo "!!!   Resetting it. EVERY BOOTH's DB_PASSWORD/MASTER_DB_PASSWORD must" >&2
    echo "!!!   match the new value or its gate stops working." >&2
    psql_super -c "ALTER ROLE \"${DB_USER}\" WITH LOGIN PASSWORD '${DB_PASSWORD}';" >/dev/null
  fi
else
  echo "    creating role ${DB_USER}"
  # No CREATEDB/CREATEROLE/SUPERUSER: this role only needs to use its own
  # database. Booths hold this password, so it is the one to keep unprivileged.
  psql_super -c "CREATE ROLE \"${DB_USER}\" WITH LOGIN PASSWORD '${DB_PASSWORD}';" >/dev/null
fi

# Database, owned by the app role so Django can run migrations against it.
if psql_super -lqt | cut -d '|' -f1 | grep -qw "${DB_NAME}"; then
  echo "    database ${DB_NAME} exists"
else
  echo "    creating database ${DB_NAME} owned by ${DB_USER}"
  psql_super -c "CREATE DATABASE \"${DB_NAME}\" OWNER \"${DB_USER}\";" >/dev/null
fi

# A database created earlier (by postgres) has postgres-owned tables, which the
# app role can read but not ALTER — so migrations would fail partway. Move
# ownership of the database and everything already in its public schema.
echo "--- ensuring ${DB_USER} owns ${DB_NAME} and its objects ---"
psql_super -c "ALTER DATABASE \"${DB_NAME}\" OWNER TO \"${DB_USER}\";" >/dev/null
psql_super -d "${DB_NAME}" -q <<SQL
GRANT ALL ON SCHEMA public TO "${DB_USER}";
DO \$do\$
DECLARE r record;
BEGIN
  -- Tables/views first. ALTER TABLE ... OWNER also moves any sequence the table
  -- owns (serial/identity columns), which is why those must NOT be altered
  -- directly: Postgres rejects that with "Sequence ... is linked to table ...",
  -- and one such error would abort this whole block leaving nothing transferred.
  FOR r IN SELECT c.relname, c.relkind FROM pg_class c
           JOIN pg_namespace n ON n.oid = c.relnamespace
           WHERE n.nspname = 'public' AND c.relkind IN ('r','p','v','m')
  LOOP
    EXECUTE format('ALTER %s public.%I OWNER TO %I',
                   CASE r.relkind WHEN 'v' THEN 'VIEW'
                                  WHEN 'm' THEN 'MATERIALIZED VIEW'
                                  ELSE 'TABLE' END,
                   r.relname, '${DB_USER}');
  END LOOP;

  -- Then only standalone sequences — ones no table column depends on.
  FOR r IN SELECT c.relname FROM pg_class c
           JOIN pg_namespace n ON n.oid = c.relnamespace
           WHERE n.nspname = 'public' AND c.relkind = 'S'
             AND NOT EXISTS (
               SELECT 1 FROM pg_depend d
               WHERE d.objid = c.oid
                 AND d.classid = 'pg_class'::regclass
                 AND d.deptype IN ('a','i')
             )
  LOOP
    EXECUTE format('ALTER SEQUENCE public.%I OWNER TO %I', r.relname, '${DB_USER}');
  END LOOP;
END
\$do\$;
SQL

# Booths reach this Postgres over the LAN, so it must listen beyond loopback.
# Warn rather than edit postgresql.conf/pg_hba.conf — that is a security call.
LISTEN="$(psql_super -tAc 'SHOW listen_addresses' 2>/dev/null || echo '?')"
if [ "$LISTEN" = "localhost" ] || [ "$LISTEN" = "127.0.0.1" ]; then
  echo "!!! WARNING: Postgres listen_addresses='${LISTEN}' — booths CANNOT reach it." >&2
  echo "!!!   Set listen_addresses='*' in postgresql.conf and add a pg_hba.conf" >&2
  echo "!!!   line for the booth subnets granting ${DB_USER} access to ${DB_NAME}," >&2
  echo "!!!   then restart postgresql. Booths are online-only: no link, no gate." >&2
fi

# ── 4. Migrate ────────────────────────────────────────────────────────────
# Deliberately NOT followed by any TRUNCATE. Master owns plazas/lanes/rates/tags.

# manage.py falls back to config.settings.local when the shell does not export
# this. .env sets it, but .env is only read from inside the settings module —
# far too late to pick which one loads. Without this, every command below ran
# under dev settings: DEBUG on, and master_pg aliased to the local database.
export DJANGO_SETTINGS_MODULE=config.settings.lan
echo "--- settings module: $DJANGO_SETTINGS_MODULE ---"

# The integer-PK refactor replaced the migration history. A database still
# recording the old migrations cannot be migrated in place — Postgres cannot
# cast uuid to bigint, and the replayed initials collide with existing tables.
# Say so plainly instead of dying later on a confusing DuplicateColumn.
echo "--- checking migration history ---"
ORPHANS="$(python - <<'PY' 2>/dev/null || true
import django
django.setup()
from django.db import connection
from django.db.migrations.loader import MigrationLoader
try:
    loader = MigrationLoader(connection, ignore_no_migrations=True)
    disk = set(loader.disk_migrations)
    print("\n".join(f"{a}.{n}" for (a, n) in sorted(loader.applied_migrations)
                    if (a, n) not in disk and a not in ("contenttypes", "auth",
                        "admin", "sessions", "token_blacklist")))
except Exception:
    pass
PY
)"
if [ -n "$ORPHANS" ]; then
  echo "!!! This database records migrations that no longer exist in the code:" >&2
  echo "$ORPHANS" | sed 's/^/!!!   /' >&2
  echo "!!!" >&2
  echo "!!! Master predates the integer-PK refactor and has no in-place upgrade" >&2
  echo "!!! path. Back it up, drop ${DB_NAME}, recreate it and re-run this script." >&2
  echo "!!! Every booth must then be redeployed with --recreate-db as well." >&2
  exit 3
fi

echo "--- running migrations ---"
python manage.py migrate --noinput

echo "--- collecting static files (admin + DRF UI) ---"
python manage.py collectstatic --noinput >/dev/null

# ── 5. Reference data: plazas, lanes, vehicle categories, fare matrix ─────
# Booths do NOT seed these — they arrive by sync — so master must hold them
# before any booth is useful. run_gate refuses to start when it cannot resolve
# its Plaza.plaza_id, and an exit cannot price a trip with an empty fare_matrix.
#
# Both commands are idempotent upserts (update_or_create) of the operator's
# real plaza list and tariff, so re-running a bootstrap re-asserts them without
# disturbing live data. Destructive cleanup only happens behind the explicit
# --drop-legacy flag, which is deliberately not used here.
echo "--- loading plazas + lanes ---"
python manage.py load_plazas --apply

echo "--- loading vehicle categories + fare matrix ---"
python manage.py load_fares --apply

PLAZA_COUNT="$(psql_admin -d "${DB_NAME}" -tAc 'SELECT COUNT(*) FROM plazas' 2>/dev/null || echo 0)"
FARE_COUNT="$(psql_admin -d "${DB_NAME}" -tAc 'SELECT COUNT(*) FROM fare_matrix' 2>/dev/null || echo 0)"
echo "--- master reference data: ${PLAZA_COUNT} plazas, ${FARE_COUNT} fares ---"
if [ "${PLAZA_COUNT:-0}" = "0" ] || [ "${FARE_COUNT:-0}" = "0" ]; then
  echo "!!! Reference data is incomplete. Booths resolve their lane by" >&2
  echo "!!!   Plaza.plaza_id and price exits from fare_matrix, so they will fail" >&2
  echo "!!!   until both are populated. Check the load_plazas/load_fares output" >&2
  echo "!!!   above before deploying any booth." >&2
else
  echo "--- plaza_id values booths can be pointed at: ---"
  psql_admin -d "${DB_NAME}" -c \
    'SELECT plaza_id, name, is_active FROM plazas ORDER BY plaza_id;'
fi

# ── 6. PM2 ────────────────────────────────────────────────────────────────
# sshpass is how mtag-deploy authenticates to a booth when BOOTH_SSH_PASSWORD is
# set in master's .env. Without it every portal-triggered booth update fails on a
# password prompt no one can answer. Best effort — a master using SSH keys
# instead does not need it, and broken apt sources must not stop the bootstrap.
if ! command -v sshpass >/dev/null 2>&1; then
  echo "--- installing sshpass (booth deploys) ---"
  sudo apt-get install -y sshpass || \
    echo "!!! sshpass install failed — portal booth updates need it unless master uses SSH keys" >&2
fi

if ! command -v pm2 >/dev/null 2>&1; then
  echo "--- pm2 not found — installing Node.js + PM2 ---"
  sudo apt-get install -y nodejs npm
  sudo npm install -g pm2
fi

echo "--- starting PM2 (gunicorn) ---"
pm2 delete mtag-master mtag-deploy >/dev/null 2>&1 || true
pm2 start ecosystem.master.config.js
pm2 save

echo ""
echo "=== Master bootstrap complete ==="
pm2 status
echo ""
echo "Verify:  pm2 logs mtag-master --lines 50"
echo "API:     curl -s http://${ALLOWED_HOST}:8000/api/v1/ | head"

#!/usr/bin/env bash
# Run THIS on your dev machine (with the VPN/LAN connection to the master server).
# Builds a fresh mtag_backend tarball, copies it to master, and runs
# mtag_backend/master_bootstrap.sh there to configure + start gunicorn.
#
# Interactive (prompts for anything not already set):
#   ./deploy_master.sh
#
# Or non-interactive:
#   MASTER_IP=192.168.78.200 SSH_USER=iteck SSH_PORT=22 \
#   DB_NAME=master_tag_db DB_PASSWORD=xxxx ./deploy_master.sh
#
# DEPLOY MASTER BEFORE THE BOOTHS. A booth's sync pulls `plaza_id` from master,
# so booths cannot sync until master has migration 0007 applied. The reverse is
# also true: once master migrates, un-updated booths fail their plaza sync
# because Plaza.code no longer exists. Do master and all booths in one window.
#
# Caveat: DB_PASSWORD is passed over SSH as part of a command line, so it's
# briefly visible via `ps` on both ends during the run. Fine for a private
# VPN/LAN deployment tool; don't reuse this for anything internet-facing.
# Avoid single-quote characters in DB_PASSWORD — the quoting below doesn't
# escape them.

set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# FILLED IN for this master. Blank any of them out ("") to be asked for it
# interactively instead when the script runs.
# ─────────────────────────────────────────────────────────────────────────────
MASTER_IP="192.168.78.200"     # master's LAN IP (SSH target + ALLOWED_HOSTS)
SSH_USER="mew02"               # SSH username on master
SSH_PORT="22"                  # SSH port
DB_NAME="master_tag_db"        # master's database name
DB_USER="postgres"             # master's DB user
DB_PASSWORD="12345678"         # master's DB password
CORS_ORIGINS="http://192.168.78.200:5173"   # portal origin(s), comma-separated.
                               # MUST be set: config.settings.lan overrides base.py
                               # with env.list(default=[]), so an empty value allows
                               # NO origin — preflights return 200 and every browser
                               # request is then silently blocked.
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

echo "=== Master deployment ==="
prompt MASTER_IP    "Master LAN IP"
prompt SSH_USER     "SSH username"
prompt SSH_PORT     "SSH port" "22"
prompt DB_NAME      "Master's database name" "master_tag_db"
prompt DB_USER      "Master's DB user" "postgres"
prompt DB_PASSWORD  "Master's DB password"

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

echo "--- Copying to $SSH_USER@$MASTER_IP:$SSH_PORT ---"
scp -P "$SSH_PORT" "$TARBALL" "$SSH_USER@$MASTER_IP:~/"

echo "--- Extracting code on master ---"
ssh -p "$SSH_PORT" "$SSH_USER@$MASTER_IP" "tar -xzf mtag_backend_deploy.tar.gz"

echo "--- Bootstrapping master ---"
echo "(master_bootstrap.sh runs several 'sudo' commands remotely — enter the"
echo " master's sudo password below if/when prompted)"
# -t allocates a pseudo-terminal so remote `sudo` can prompt for a password.
# shellcheck disable=SC2087
ssh -t -p "$SSH_PORT" "$SSH_USER@$MASTER_IP" "
  cd mtag_backend &&
  DB_NAME='$DB_NAME' \
  DB_USER='$DB_USER' \
  DB_PASSWORD='$DB_PASSWORD' \
  CORS_ORIGINS='$CORS_ORIGINS' \
  ALLOWED_HOST='$MASTER_IP' \
  bash master_bootstrap.sh
"

echo ""
echo "=== Master deployed ($MASTER_IP) ==="
echo "Next:"
echo "  1. Confirm the plaza_id list printed above matches your operator numbering."
echo "     If not, edit PLAZAS in apps/tolls/plaza_registry.py, re-run"
echo "     'python manage.py load_plazas --apply', and re-check BEFORE any booth."
echo "  2. Deploy each booth:  ./deploy_booth.sh"
echo "  3. Per booth, confirm sync:  python manage.py trip_sync   (DRIFT must be 0)"
echo "SSH in to double-check: ssh -p $SSH_PORT $SSH_USER@$MASTER_IP"

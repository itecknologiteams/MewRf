#!/usr/bin/env bash
# Deploy the operator portal (rfid-frontend) to master.
#
# Run on your dev machine. Builds rfid-frontend/, rsyncs the compiled bundle to
# master and moves it into the Apache web root served on :8081.
#
#   ./deploy_frontend.sh                 # build, then deploy
#   ./deploy_frontend.sh --skip-build    # deploy the existing dist/ as-is
#   ./deploy_frontend.sh --dry-run       # show what would change on master, stop
#   ./deploy_frontend.sh --host 10.0.0.5 # override the target
#
# The vhost itself (deploy/apache-rfid-portal.conf) is a ONE-TIME setup and this
# script does not touch it. It only replaces the static files, so it never
# restarts Apache and never interrupts a request in flight.
#
# This is independent of deploy_master.sh: the portal is static files, the API is
# gunicorn. A UI change needs only this script. A change that also alters the API
# needs deploy_master.sh FIRST — the new bundle may call endpoints the running
# backend does not have yet.

set -uo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Master's LAN address. The portal is a LAN-only tool, so this is the IP the
# booths and operator workstations already use. SSH goes here too.
MASTER_HOST="192.168.78.200"
SSH_USER="mew02"

# 22, not the 1122 that deploy_master.sh uses. 1122 is master's PUBLIC SSH port;
# on the LAN interface it is refused, and the connection dies with "connection
# refused" that reads like the host is down.
SSH_PORT="22"

# Apache's DocumentRoot from deploy/apache-rfid-portal.conf. Owned by www-data,
# so the copy into it goes through sudo below.
WEB_ROOT="/var/www/rfid-portal"

# Where the bundle lands on master before it is moved into WEB_ROOT. Under the
# SSH user's home so the first rsync needs no privileges at all — only the short
# second step does.
STAGING="rfid-portal-staging"

PORTAL_PORT="8081"             # what the vhost listens on; used by the checks at the end.

# SSH password. Left empty on purpose so this file stays committable. Supply it
# per-run if you have no keys installed:
#     MASTER_SSH_PASSWORD='...' ./deploy_frontend.sh
SSH_PASSWORD="${MASTER_SSH_PASSWORD:-}"
# ─────────────────────────────────────────────────────────────────────────────

SKIP_BUILD=0
DRY_RUN=0
while [ $# -gt 0 ]; do
  case "$1" in
    --host)       MASTER_HOST="$2"; shift 2 ;;
    --user)       SSH_USER="$2"; shift 2 ;;
    --port)       SSH_PORT="$2"; shift 2 ;;
    --web-root)   WEB_ROOT="$2"; shift 2 ;;
    --skip-build) SKIP_BUILD=1; shift ;;
    --dry-run)    DRY_RUN=1; shift ;;
    -h|--help)    sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "ERROR: unknown flag $1 (try --help)" >&2; exit 1 ;;
  esac
done

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$REPO_DIR/rfid-frontend"
DIST_DIR="$FRONTEND_DIR/dist"

# sshpass wrapper; empty when no password is set so ssh/rsync behave normally.
SSH_WRAP=()
if [ -n "$SSH_PASSWORD" ]; then
  if ! command -v sshpass >/dev/null 2>&1; then
    echo "ERROR: MASTER_SSH_PASSWORD is set but sshpass is not installed." >&2
    echo "       sudo apt-get install -y sshpass" >&2
    exit 1
  fi
  export SSHPASS="$SSH_PASSWORD"
  SSH_WRAP=(sshpass -e)
fi
SSH=("${SSH_WRAP[@]}" ssh -p "$SSH_PORT" -o StrictHostKeyChecking=accept-new)

# ── build ────────────────────────────────────────────────────────────────────
if [ "$SKIP_BUILD" -eq 0 ]; then
  echo "==> building rfid-frontend"
  # `npm run build` is `tsc -b && vite build` — a type error stops it before any
  # output is written, so a failure here leaves the last good dist/ untouched.
  if ! (cd "$FRONTEND_DIR" && npm run build); then
    echo "ERROR: build failed; nothing was deployed." >&2
    exit 1
  fi
else
  echo "==> skipping build, using the existing dist/"
fi

if [ ! -f "$DIST_DIR/index.html" ]; then
  echo "ERROR: $DIST_DIR/index.html does not exist. Run without --skip-build." >&2
  exit 1
fi

# The bundle must reference its assets at an ABSOLUTE /assets/ path. The app uses
# BrowserRouter, so a relative base resolves against the current path: index.html
# loaded at /booth/12 asks for /booth/assets/index-*.js and the page comes up
# blank. Catch that here rather than after it is live.
if ! grep -q '"/assets/' "$DIST_DIR/index.html"; then
  echo "ERROR: dist/index.html does not reference /assets/ absolutely." >&2
  echo "       Was VITE_BASE set to something relative? See vite.config.ts." >&2
  exit 1
fi

BUNDLE="$(grep -oE '/assets/index-[A-Za-z0-9_-]+\.js' "$DIST_DIR/index.html" | head -1)"
echo "==> bundle: $BUNDLE"

# ── stage on master ──────────────────────────────────────────────────────────
RSYNC_FLAGS=(-az --delete --human-readable)
[ "$DRY_RUN" -eq 1 ] && RSYNC_FLAGS+=(--dry-run --itemize-changes)

echo "==> syncing dist/ to $SSH_USER@$MASTER_HOST:~/$STAGING/"
if ! "${SSH_WRAP[@]}" rsync "${RSYNC_FLAGS[@]}" \
      -e "ssh -p $SSH_PORT -o StrictHostKeyChecking=accept-new" \
      "$DIST_DIR/" "$SSH_USER@$MASTER_HOST:$STAGING/"; then
  echo "ERROR: rsync to master failed; the live portal is unchanged." >&2
  exit 1
fi

if [ "$DRY_RUN" -eq 1 ]; then
  echo
  echo "Dry run: staged copy only, $WEB_ROOT was not touched."
  exit 0
fi

# ── move into the web root ───────────────────────────────────────────────────
# -t because sudo prompts for a password: mew02 is in the sudo group but has no
# NOPASSWD rule, and without a TTY the prompt cannot be answered and the command
# fails with "sudo: a terminal is required".
echo "==> installing into $WEB_ROOT (enter master's sudo password if prompted)"
"${SSH[@]}" -t "$SSH_USER@$MASTER_HOST" "
  set -e
  if [ ! -f \"\$HOME/$STAGING/index.html\" ]; then
    echo \"ERROR: \$HOME/$STAGING/index.html is missing on master.\" >&2
    exit 1
  fi
  sudo mkdir -p '$WEB_ROOT'

  # --delete-after, not plain --delete: it writes the new files FIRST and removes
  # the stale ones at the end. With deletions first, the old index-*.js is gone
  # for the length of the transfer and anyone loading the portal in that window
  # gets a blank page.
  #
  # Deleting the previous bundle at all is safe only because the vhost sends
  # index.html as no-cache — a browser always re-reads it and asks for the NEW
  # asset name. Cache index.html and this line strands every open tab.
  # \$HOME in DOUBLE quotes, not single: the remote shell must expand it. Single
  # quotes send rsync the literal string \$HOME, which it resolves against the cwd
  # and fails with 'change_dir "/home/mew02/\$HOME/..." failed'.
  sudo rsync -a --delete-after \"\$HOME/$STAGING/\" '$WEB_ROOT/'
  sudo chown -R www-data:www-data '$WEB_ROOT'
"
RC=$?
if [ $RC -ne 0 ]; then
  echo "ERROR: install on master failed (exit $RC)." >&2
  echo "       The staged copy is at ~/$STAGING on master; nothing was lost." >&2
  exit 1
fi

# ── verify ───────────────────────────────────────────────────────────────────
# Checked over HTTP from this machine, not by listing files on master: that is
# what an operator's browser actually does, and it exercises Apache's config too.
echo
echo "==> verifying http://$MASTER_HOST:$PORTAL_PORT"
BASE="http://$MASTER_HOST:$PORTAL_PORT"
FAIL=0
check() { # label url expected
  code="$(curl -s -o /dev/null -w '%{http_code}' -m 10 "$2")"
  if [ "$code" = "$3" ]; then
    printf '    ok   %-34s %s\n' "$1" "$code"
  else
    printf '    FAIL %-34s %s (expected %s)\n' "$1" "$code" "$3"; FAIL=1
  fi
}
check "index"                  "$BASE/"                     200
# A client-side route with no file behind it. 404 here means the vhost's SPA
# fallback is missing and every deep link and refresh is broken.
check "SPA fallback (/plazas)" "$BASE/plazas"               200
# 401, not 200: unauthenticated is the CORRECT answer and proves Apache reached
# Django. A 404 or 502 means the /api/ proxy is not wired up, and the portal will
# log in and then spin forever.
check "api proxy (/auth/me/)"  "$BASE/api/v1/auth/me/"      401
check "new bundle is served"   "$BASE$BUNDLE"               200

echo
if [ "$FAIL" -eq 0 ]; then
  echo "Deployed. Open $BASE and hard-refresh (Ctrl-Shift-R) once."
else
  echo "Deployed, but a check failed — see above. Apache logs on master:" >&2
  echo "  sudo tail -50 /var/log/apache2/rfid-portal-error.log" >&2
  exit 1
fi

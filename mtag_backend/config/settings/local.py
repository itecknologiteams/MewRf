from .base import *

DEBUG = True

# Dev: accept any host so the server is reachable via its LAN IP
# (192.168.78.249 / 192.168.21.233), not just localhost.
ALLOWED_HOSTS = ['*']

CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',
    'http://localhost:3000',
    'http://127.0.0.1:5173',
    'http://127.0.0.1:3000',
]
# Dev convenience: allow localhost AND any private-LAN IP (192.168.x.x /
# 10.x.x.x) on any port, so the frontend served from a network IP isn't blocked
# by CORS. Dev/local only.
CORS_ALLOWED_ORIGIN_REGEXES = [
    r'^http://localhost:\d+$',
    r'^http://127\.0\.0\.1:\d+$',
    r'^http://192\.168\.\d+\.\d+:\d+$',
    r'^http://10\.\d+\.\d+\.\d+:\d+$',
]

# ── Isolate local dev from the production master ──────────────────────────────
# Never auto-start the bidirectional sync agent on a dev machine.
ANPR_GATE_ENABLED = False
# Defence-in-depth: even an explicit/manual sync or the exit-time master fallback
# must stay on localhost — never reach 192.168.78.200.
DATABASES['master_pg'] = DATABASES['local_pg']

# ── TEMPORARY (testing only) ──────────────────────────────────────────────────
# Auto-clear a vehicle's existing active trip on each entry, so the same tag can
# re-enter repeatedly without manually resetting the trip (exit not wired yet).
# Only here (dev/local); production `lan` settings never sets this, so prod keeps
# the normal "already has an active trip" guard. Remove when exit works.
ENTRY_AUTO_RESET_ACTIVE_TRIP = True

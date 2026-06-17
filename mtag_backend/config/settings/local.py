from .base import *

DEBUG = True
CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',
    'http://localhost:3000',
    'http://127.0.0.1:5173',
    'http://127.0.0.1:3000',
]
# Dev convenience: allow any localhost port (3000, 3001, 5173, ...) so a busy
# port (Vite falling back to 3001) doesn't break CORS. Dev/local only.
CORS_ALLOWED_ORIGIN_REGEXES = [
    r'^http://localhost:\d+$',
    r'^http://127\.0\.0\.1:\d+$',
]

# ── Isolate local dev from the production master ──────────────────────────────
# Never auto-start the bidirectional sync agent on a dev machine.
SYNC_AGENT_ENABLED = False
# Defence-in-depth: even an explicit/manual sync or the exit-time master fallback
# must stay on localhost — never reach 192.168.78.200.
DATABASES['master_pg'] = DATABASES['local_pg']

# ── TEMPORARY (testing only) ──────────────────────────────────────────────────
# Auto-clear a vehicle's existing active trip on each entry, so the same tag can
# re-enter repeatedly without manually resetting the trip (exit not wired yet).
# Only here (dev/local); production `lan` settings never sets this, so prod keeps
# the normal "already has an active trip" guard. Remove when exit works.
ENTRY_AUTO_RESET_ACTIVE_TRIP = True

"""
Sync agent loop — mode-driven, and deliberately NOT auto-started.

This runs as its own process (`manage.py sync_service`, PM2 app `mtag-sync`), not
inside the web app or the gate. The gate reads and writes only its local
database; this agent is the sole thing that talks to master. A master outage
therefore degrades reporting, never the barrier.

Mode comes from GATE_MODE in .env:

    GATE_MODE=entry   push + pull(reference, closed trips)
    GATE_MODE=exit    push + pull(reference, closed trips, OPEN trips)

Why an entry booth still pulls: it needs tags/vehicles/accounts to validate a
vehicle at all, and it needs closed trips or a finished trip stays 'active' in
its local DB and blocks that vehicle's next entry. What it does NOT need is other
plazas' OPEN trips — it never charges against them. That is the real entry/exit
difference, and it is what `include_open` controls.

Why both modes push: an entry booth must publish the trips it starts; an exit
booth must publish the exits, balances and transactions it completes.
"""
import logging
import threading
import time

from django.conf import settings

from apps.tolls.sync.pull_service import run_pull
from apps.tolls.sync.push_service import run_push

log = logging.getLogger('apps.tolls.sync.agent')

SYNC_INTERVAL = 30  # seconds
VALID_MODES = ('entry', 'exit')

_started = False
_lock = threading.Lock()


def get_mode() -> str:
    """Resolve booth mode from settings/.env, defaulting to the safe superset.

    Falls back to 'exit' on anything unrecognised: an exit booth that wrongly
    behaves like an entry booth starves itself of open trips and turns paying
    vehicles away, whereas an entry booth doing an exit booth's pull merely does
    a little extra work. Degrade toward doing more, not less.
    """
    mode = str(getattr(settings, 'GATE_MODE', '') or '').strip().lower()
    if mode not in VALID_MODES:
        log.warning(
            "[sync] GATE_MODE=%r is not one of %s — defaulting to 'exit' "
            "(the superset). Set GATE_MODE in .env to silence this.",
            mode, VALID_MODES,
        )
        return 'exit'
    return mode


def run_cycle(mode: str = None) -> dict:
    """One pull+push cycle. Returns {'mode', 'pull', 'push'}.

    Pull runs before push so this booth is working from master's latest view
    before it publishes its own changes — it means an exit booth sees an entry
    made elsewhere in the same cycle it charges for it.
    """
    mode = mode or get_mode()
    pull_result = run_pull(mode)
    push_result = run_push()
    return {'mode': mode, 'pull': pull_result, 'push': push_result}


def _loop():
    mode = get_mode()
    log.info("[sync] Agent started — mode=%s interval=%ds", mode, SYNC_INTERVAL)
    while True:
        try:
            result = run_cycle(mode)
            if result['pull'].get('error') or result['push'].get('error'):
                log.warning("[sync] %s", result)
            else:
                log.debug("[sync] %s", result)
        except Exception as exc:
            log.error("[sync] Unexpected error: %s", exc)
        time.sleep(SYNC_INTERVAL)


def start():
    """Start the agent in a background thread. Safe to call repeatedly.

    Kept for embedded use, but the supported deployment is the standalone
    `manage.py sync_service` process — see this module's docstring.
    """
    global _started
    with _lock:
        if _started:
            return
        _started = True
    threading.Thread(target=_loop, name='pg-sync-agent', daemon=True).start()
    log.info("[sync] Background thread started")

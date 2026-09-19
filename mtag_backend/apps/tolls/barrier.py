"""How the gate raises the barrier: through the local barrier service, or the
serial port directly.

Booths run qtserver-v2-new, whose barrierServer.ts holds /dev/ttyUSB0 open for
the life of the process and exposes an HTTP API on 127.0.0.1:3005. Writing to
the same tty from run_gate as well means two processes interleaving bytes on one
relay — so where that service exists, it is the only thing that touches serial
and the gate asks it instead.

Not every booth necessarily runs it, so the backend is chosen by probing at
startup rather than configured per booth across the fleet:

    service answers  →  HTTP, and the serial port is never opened
    no answer        →  serial, exactly as before, re-probing in the background
                        so a booth switches over once the service comes up

Two ways to raise it, and the difference matters:

    open()             one pulse — the service writes 'o', waits
                       BARRIER_CLOSE_DELAY and writes 'f' itself. Right for a
                       single vehicle. There is no separate close to send, and
                       sending one would shut a barrier the service still
                       considers open; hence a close() that no-ops in service
                       mode, and `cycle_seconds` for callers doing their own
                       sequencing.

    hold() / release() the boom goes up and stays up until released. Right for a
                       convoy, where pulsing per vehicle drops the barrier
                       between cars that are still moving through it.

Commands run through one FIFO worker rather than a thread per call. Ordering is
the whole point: a hold and a release dispatched concurrently can land in either
order, and losing that race leaves the boom up with nothing scheduled to drop
it. A queue also keeps callers unblocked, which matters because a service `open`
does not answer until the relay pulse has finished.
"""

import json
import queue
import threading
import time
import urllib.error
import urllib.request

DEFAULT_SERVICE_URL = 'http://127.0.0.1:3005'
STATUS_PATH = '/api/external/status'
CONTROL_PATH = '/api/external/barrier'

# The service answers a status probe in milliseconds when it is up; a longer
# wait here would just delay gate startup on booths that do not run it.
PROBE_TIMEOUT = 2.0
# An open request does not return until the relay pulse has finished, so this
# has to clear BARRIER_CLOSE_DELAY (500ms on the booths) with room to spare.
# Generous on purpose: it is a ceiling for a wedged service, not a target.
OPEN_TIMEOUT = 15.0
# hold and release answer as soon as the byte is written — no relay wait.
COMMAND_TIMEOUT = 5.0
# How long cleanup() waits for queued commands to finish posting.
CLEANUP_DRAIN_TIMEOUT = 10.0
REPROBE_SECONDS = 30.0
# The service closes after its own delay; the gate's local timer must not expire
# first or it releases the next car into a barrier that is still down.
SERVICE_CYCLE_MARGIN = 0.5


class BarrierBackend:
    """Opens the barrier by whichever route this booth actually has."""

    def __init__(
        self, *, serial_port, serial_baud, open_secs, stdout,
        service_url=DEFAULT_SERVICE_URL, service_cycle_secs=0.5,
        prefer_service=True,
    ):
        self.stdout = stdout
        self.service_url = service_url.rstrip('/')
        self.service_cycle_secs = service_cycle_secs
        self._serial_port = serial_port
        self._serial_baud = serial_baud
        self._open_secs = open_secs

        self._serial = None
        self._mode = 'serial'
        self._lock = threading.Lock()
        self._running = True

        # Service commands are posted by one worker so they reach the service in
        # the order the gate issued them. See the module docstring.
        self._cmd_q: queue.Queue = queue.Queue()
        self._cmd_worker = threading.Thread(target=self._drain_commands, daemon=True)
        self._cmd_worker.start()

        if prefer_service and self._probe():
            self._mode = 'service'
            self.stdout.write(
                f"[barrier] Using barrier service at {self.service_url} "
                f"— serial port left to it"
            )
        else:
            if prefer_service:
                self.stdout.write(
                    f"[barrier] No barrier service at {self.service_url} "
                    f"— driving {serial_port} directly"
                )
            self._setup_serial()
            # Only worth watching for when we are the one holding the tty.
            threading.Thread(target=self._watch_for_service, daemon=True).start()

    # ── What callers need to know ────────────────────────────────────────────

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def cycle_seconds(self) -> float:
        """How long one open→close cycle takes, whoever is performing it.

        In service mode this is the service's own BARRIER_CLOSE_DELAY, not the
        booth's open_seconds — the gate must not release the next car while the
        service still has the barrier up.
        """
        if self._mode == 'service':
            return max(self._open_secs, self.service_cycle_secs + SERVICE_CYCLE_MARGIN)
        return self._open_secs

    # ── Commands ─────────────────────────────────────────────────────────────

    def open(self, metadata=None, source='rfid') -> bool:
        """Raise the barrier for one vehicle, letting it close on its own.

        Returns whether the command was dispatched, not whether the boom moved —
        the same guarantee a serial write gave: bytes left, the relay may or may
        not have followed. In service mode the HTTP call does not answer until
        the barrier has closed again, so it is queued rather than awaited; the
        reader thread that calls this must not stall for a relay pulse.
        """
        if self._mode == 'service':
            self._cmd_q.put('open')
            return True
        return self._write('o')

    def hold(self, metadata=None, source='rfid') -> bool:
        """Raise the barrier and leave it up until release() is called.

        For a convoy: several authorised vehicles moving through one opening.
        The caller owns the closing, and must call release() — nothing here will
        do it for them.
        """
        if self._mode == 'service':
            self._cmd_q.put('hold')
            return True
        return self._write('o')

    def release(self) -> bool:
        """Drop a barrier raised by hold()."""
        if self._mode == 'service':
            self._cmd_q.put('release')
            return True
        return self._write('f')

    def close(self) -> bool:
        """Close a barrier raised by open() — a no-op when the service owns it.

        The service schedules its own 'f' after BARRIER_CLOSE_DELAY. Sending one
        here would either race that or, worse, drop the barrier on a vehicle
        while the service still believes it is open. This is not the counterpart
        to hold(); that is release(), which the service does honour.
        """
        if self._mode == 'service':
            return True
        return self._write('f')

    def _drain_commands(self):
        """Post queued service commands one at a time, in order.

        Deliberately not guarded by `_running`: shutdown queues a release behind
        whatever is already pending, and a worker that stopped on the flag would
        drop it and leave the boom up. The sentinel is the only way out, and it
        arrives last.
        """
        while True:
            action = self._cmd_q.get()
            if action is None:
                return
            self._service_call(action)

    def _service_call(self, action: str) -> bool:
        # Deliberately the bare payload — `action` and nothing else, matching the
        # request verified by hand against a booth. The service accepts optional
        # `source` and `metadata` and echoes them into its own barrier.log, but
        # they are not sent: keeping the request minimal removes the payload as a
        # variable when a lane misbehaves. Restore them here if the barrier.log
        # audit trail is wanted back.
        timeout = OPEN_TIMEOUT if action == 'open' else COMMAND_TIMEOUT
        try:
            body = self._post(CONTROL_PATH, {'action': action}, timeout)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            self.stdout.write(f"[barrier] Service {action} failed: {exc}")
            return False

        if body.get('success'):
            return True
        # The service refuses an overlapping open rather than queueing it, so
        # this is the expected answer when a cycle is already running — say which
        # it was instead of a bare failure.
        self.stdout.write(
            f"[barrier] Service refused the {action}: {body.get('error') or body}"
        )
        return False

    def _service_open(self, metadata=None, source='rfid') -> bool:
        """Post one open synchronously. The queue worker's usual entry point."""
        return self._service_call('open')

    def _post(self, path, payload, timeout) -> dict:
        data = json.dumps(payload).encode()
        request = urllib.request.Request(
            f"{self.service_url}{path}", data=data, method='POST',
            headers={'Content-Type': 'application/json'},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode() or '{}')

    # ── Service discovery ────────────────────────────────────────────────────

    def _probe(self) -> bool:
        try:
            request = urllib.request.Request(f"{self.service_url}{STATUS_PATH}")
            with urllib.request.urlopen(request, timeout=PROBE_TIMEOUT) as response:
                body = json.loads(response.read().decode() or '{}')
        except (urllib.error.URLError, OSError, ValueError):
            return False
        # A service whose own serial port is shut cannot raise anything, so it
        # is no better than not being there — keep driving the port ourselves.
        status = body.get('status') or {}
        return bool(body.get('success')) and bool(status.get('isOpen', True))

    def _watch_for_service(self):
        """Hand the port over if the service appears after we started.

        A booth that boots with qtserver still starting would otherwise stay on
        serial until the next gate restart, with both processes on the tty the
        whole time.
        """
        while self._running and self._mode == 'serial':
            time.sleep(REPROBE_SECONDS)
            if not self._running or self._mode != 'serial':
                return
            if self._probe():
                with self._lock:
                    if self._mode != 'serial':
                        return
                    self._mode = 'service'
                    self._close_serial()
                self.stdout.write(
                    f"[barrier] Barrier service appeared at {self.service_url} "
                    f"— released {self._serial_port} and switched to it"
                )
                return

    # ── Serial ───────────────────────────────────────────────────────────────

    def _setup_serial(self) -> bool:
        try:
            import serial
            self._serial = serial.Serial(
                port=self._serial_port, baudrate=self._serial_baud, timeout=1,
            )
            self.stdout.write(
                f"[serial] Connected on {self._serial_port} at {self._serial_baud} baud"
            )
            return True
        except Exception as exc:
            self.stdout.write(f"[serial] Not available ({exc}) — barrier control disabled")
            self._serial = None
            return False

    def _write(self, cmd: str) -> bool:
        """Write one command byte, reopening the port if it has gone away.

        The port is not guaranteed to survive the life of the process. A USB
        relay that browns out or re-enumerates takes /dev/ttyUSB0 with it, and
        the write that discovers this fails. The old code responded by setting
        _serial = None — and nothing ever set it back, so the barrier was dead
        until someone restarted the gate, even though the port came back
        seconds later. A booth that started before its relay was plugged in was
        likewise stuck with "barrier control disabled" forever.

        So a write now reopens first if it has to, and retries once if the write
        itself is what failed: the second attempt runs on a freshly opened port.
        """
        for attempt in (1, 2):
            if self._serial is None or not self._serial.is_open:
                if not self._setup_serial():
                    return False          # port genuinely absent — already logged
            try:
                self._serial.write(cmd.encode())
                return True
            except Exception as exc:
                self.stdout.write(
                    f"[serial] Write error on attempt {attempt}: {exc}"
                )
                self._close_serial()      # forces a reopen on the next pass
        self.stdout.write(
            f"[serial] Could not write '{cmd}' to {self._serial_port} — "
            f"THE BARRIER DID NOT MOVE"
        )
        return False

    def _close_serial(self):
        try:
            if self._serial and self._serial.is_open:
                self._serial.close()
        except Exception as exc:
            self.stdout.write(f"[serial] Close error: {exc}")
        self._serial = None

    def cleanup(self):
        """Stop, having posted everything still queued — a release included."""
        self._running = False
        self._cmd_q.put(None)
        # Bounded: a wedged service must not stop the gate from exiting, but a
        # release sitting in the queue is worth waiting out.
        self._cmd_worker.join(timeout=CLEANUP_DRAIN_TIMEOUT)
        self._close_serial()

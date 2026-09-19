"""Barrier backend selection: the local barrier service vs. the serial port.

The thing being protected here is that two processes never write to the same
tty. qtserver-v2-new's barrierServer holds /dev/ttyUSB0 open for its whole life,
so when it is present the gate must not open the port at all.
"""

import json
import threading
import time
import urllib.error
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.tolls import barrier as barrier_mod
from apps.tolls.barrier import BarrierBackend


class _Sink:
    def __init__(self):
        self.lines = []

    def write(self, msg):
        self.lines.append(msg)

    def text(self):
        return '\n'.join(self.lines)


class _Response:
    """Stands in for the object urlopen yields as a context manager."""

    def __init__(self, payload):
        self._body = json.dumps(payload).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


UP = {'success': True, 'status': {'isOpen': True, 'isSequenceActive': False}}


def _backend(sink, **kwargs):
    opts = dict(
        serial_port='/dev/ttyUSB0', serial_baud=115200,
        open_secs=2.0, stdout=sink,
    )
    opts.update(kwargs)
    return BarrierBackend(**opts)


class ServiceDetectedTests(SimpleTestCase):
    """A booth running qtserver-v2-new."""

    def setUp(self):
        self.sink = _Sink()
        self.serial = MagicMock()

    def _up(self, *_a, **_k):
        return _Response(UP)

    def test_serial_port_is_never_opened(self):
        """The whole point: barrierServer owns the tty, so we must not touch it."""
        with patch('urllib.request.urlopen', self._up), \
             patch.dict('sys.modules', {'serial': self.serial}):
            backend = _backend(self.sink)
        self.assertEqual(backend.mode, 'service')
        self.serial.Serial.assert_not_called()
        self.assertIn('Using barrier service', self.sink.text())

    def test_open_posts_the_bare_external_api_payload(self):
        """Only `action` goes on the wire, even when the caller supplies more.

        The service accepts `source` and `metadata`, but the gate sends neither:
        the request is kept byte-identical to the one verified by hand against a
        booth, so a misbehaving lane cannot be blamed on the payload.
        """
        posted = {}

        def fake_urlopen(request, timeout=None):
            posted['url'] = request.full_url
            posted['method'] = request.method
            posted['body'] = json.loads(request.data.decode()) if request.data else None
            return _Response({'success': True, 'action': 'open'})

        with patch('urllib.request.urlopen', self._up):
            backend = _backend(self.sink)
        with patch('urllib.request.urlopen', fake_urlopen):
            backend._service_open({'tagId': 'ABC123'})

        self.assertEqual(posted['url'], 'http://127.0.0.1:3005/api/external/barrier')
        self.assertEqual(posted['method'], 'POST')
        self.assertEqual(posted['body'], {'action': 'open'})

    def test_open_does_not_block_the_caller(self):
        """The HTTP call only returns once the barrier has closed — seconds.

        on_tag runs on the reader thread; waiting there would stall tag reads
        for the length of every barrier cycle.
        """
        released = threading.Event()
        entered = threading.Event()

        def slow_urlopen(request, timeout=None):
            entered.set()
            released.wait(5)
            return _Response({'success': True})

        with patch('urllib.request.urlopen', self._up):
            backend = _backend(self.sink)
        with patch('urllib.request.urlopen', slow_urlopen):
            self.assertTrue(backend.open())          # returns immediately
            self.assertTrue(entered.wait(2))          # the request did go out
            released.set()

    def test_hold_and_release_reach_the_service_in_order(self):
        """A release overtaking its own hold leaves the boom up for good.

        Both are dispatched without blocking the caller, so ordering cannot come
        from the callers racing to make the request themselves.
        """
        posted = []
        in_flight = threading.Event()

        def fake_urlopen(request, timeout=None):
            action = json.loads(request.data.decode())['action']
            if action == 'hold':
                in_flight.set()
                time.sleep(0.2)   # release gets queued while this is still out
            posted.append(action)
            return _Response({'success': True})

        with patch('urllib.request.urlopen', self._up):
            backend = _backend(self.sink)
        with patch('urllib.request.urlopen', fake_urlopen):
            self.assertTrue(backend.hold())
            self.assertTrue(in_flight.wait(2))
            self.assertTrue(backend.release())
            backend.cleanup()

        self.assertEqual(posted, ['hold', 'release'])

    def test_cleanup_posts_a_release_that_is_still_queued(self):
        """Shutdown must not strand a raised boom."""
        posted = []

        def fake_urlopen(request, timeout=None):
            posted.append(json.loads(request.data.decode())['action'])
            return _Response({'success': True})

        with patch('urllib.request.urlopen', self._up):
            backend = _backend(self.sink)
        with patch('urllib.request.urlopen', fake_urlopen):
            backend.release()
            backend.cleanup()

        self.assertIn('release', posted)

    def test_close_is_a_no_op(self):
        """barrierServer sends its own 'f'; a second one drops the barrier early."""
        posted = []

        def fake_urlopen(request, timeout=None):
            posted.append(request.full_url)
            return _Response(UP)

        with patch('urllib.request.urlopen', self._up):
            backend = _backend(self.sink)
        with patch('urllib.request.urlopen', fake_urlopen):
            self.assertTrue(backend.close())
        self.assertEqual(posted, [], "close must not reach the service or the port")

    def test_cycle_seconds_clears_the_services_own_delay(self):
        """Whatever the pulse width is, the gate must not out-pace the service."""
        with patch('urllib.request.urlopen', self._up):
            backend = _backend(self.sink, open_secs=2.0, service_cycle_secs=3.0)
        self.assertGreater(backend.cycle_seconds, 3.0)

    def test_the_default_matches_the_booths_relay_pulse(self):
        """BARRIER_CLOSE_DELAY is 500ms on the booths, so the default is 0.5.

        Booth rfid_config.ini files predate these keys, so the code fallback is
        what every booth actually runs — a stale default here would pace every
        lane to a pulse width the service no longer uses.
        """
        with patch('urllib.request.urlopen', self._up):
            backend = _backend(self.sink, open_secs=0.0)
        self.assertEqual(backend.cycle_seconds, 0.5 + barrier_mod.SERVICE_CYCLE_MARGIN)

    def test_a_longer_local_open_seconds_still_wins(self):
        with patch('urllib.request.urlopen', self._up):
            backend = _backend(self.sink, open_secs=10.0, service_cycle_secs=3.0)
        self.assertEqual(backend.cycle_seconds, 10.0)

    def test_refused_overlapping_open_is_reported(self):
        """The service rejects a second open rather than queueing it."""
        with patch('urllib.request.urlopen', self._up):
            backend = _backend(self.sink)
        with patch('urllib.request.urlopen',
                   lambda *a, **k: _Response({'success': False, 'error': 'Failed to open barrier'})):
            self.assertFalse(backend._service_open({}))
        self.assertIn('refused', self.sink.text())

    def test_unreachable_service_during_open_is_reported_not_raised(self):
        with patch('urllib.request.urlopen', self._up):
            backend = _backend(self.sink)
        with patch('urllib.request.urlopen',
                   side_effect=urllib.error.URLError('connection refused')):
            self.assertFalse(backend._service_open({}))
        self.assertIn('Service open failed', self.sink.text())


class SerialFallbackTests(SimpleTestCase):
    """A booth with no barrier service — behaviour must be exactly as before."""

    def setUp(self):
        self.sink = _Sink()
        self.serial = MagicMock()
        self.port = self.serial.Serial.return_value
        self.port.is_open = True

    def _down(self, *_a, **_k):
        raise urllib.error.URLError('connection refused')

    def test_falls_back_to_the_serial_port(self):
        with patch('urllib.request.urlopen', self._down), \
             patch.dict('sys.modules', {'serial': self.serial}):
            backend = _backend(self.sink)
        self.assertEqual(backend.mode, 'serial')
        self.serial.Serial.assert_called_once_with(
            port='/dev/ttyUSB0', baudrate=115200, timeout=1,
        )

    def test_open_and_close_write_the_original_bytes(self):
        with patch('urllib.request.urlopen', self._down), \
             patch.dict('sys.modules', {'serial': self.serial}):
            backend = _backend(self.sink)
            self.assertTrue(backend.open())
            self.assertTrue(backend.close())
        self.assertEqual(
            [c.args[0] for c in self.port.write.call_args_list], [b'o', b'f'],
        )

    def test_hold_and_release_write_the_original_bytes(self):
        """With no service, a hold is just 'o' held by nobody closing it."""
        with patch('urllib.request.urlopen', self._down), \
             patch.dict('sys.modules', {'serial': self.serial}):
            backend = _backend(self.sink)
            self.assertTrue(backend.hold())
            self.assertTrue(backend.release())
        self.assertEqual(
            [c.args[0] for c in self.port.write.call_args_list], [b'o', b'f'],
        )

    def test_cycle_seconds_is_the_configured_open_seconds(self):
        with patch('urllib.request.urlopen', self._down), \
             patch.dict('sys.modules', {'serial': self.serial}):
            backend = _backend(self.sink, open_secs=2.0)
        self.assertEqual(backend.cycle_seconds, 2.0)

    def test_missing_serial_device_disables_control_without_crashing(self):
        self.serial.Serial.side_effect = OSError('No such file or directory')
        with patch('urllib.request.urlopen', self._down), \
             patch.dict('sys.modules', {'serial': self.serial}):
            backend = _backend(self.sink)
        self.assertFalse(backend.open())
        self.assertIn('barrier control disabled', self.sink.text())

    def test_a_service_answering_with_a_shut_port_is_not_used(self):
        """It cannot raise anything, so we are better off driving the tty."""
        shut = {'success': True, 'status': {'isOpen': False}}
        with patch('urllib.request.urlopen', lambda *a, **k: _Response(shut)), \
             patch.dict('sys.modules', {'serial': self.serial}):
            backend = _backend(self.sink)
        self.assertEqual(backend.mode, 'serial')

    def test_mode_serial_never_probes(self):
        """An explicit opt-out must not depend on the service being down."""
        with patch('urllib.request.urlopen', lambda *a, **k: _Response(UP)) as _, \
             patch.dict('sys.modules', {'serial': self.serial}):
            backend = _backend(self.sink, prefer_service=False)
        self.assertEqual(backend.mode, 'serial')


class HandoverTests(SimpleTestCase):
    """The gate started first; the service came up afterwards."""

    def setUp(self):
        self.sink = _Sink()
        self.serial = MagicMock()
        self.port = self.serial.Serial.return_value
        self.port.is_open = True

    def test_switches_to_the_service_and_releases_the_tty(self):
        with patch('urllib.request.urlopen',
                   side_effect=urllib.error.URLError('down')), \
             patch.dict('sys.modules', {'serial': self.serial}):
            backend = _backend(self.sink)
        self.assertEqual(backend.mode, 'serial')

        # Drive one watcher iteration by hand rather than waiting 30s for it.
        with patch.object(barrier_mod, 'REPROBE_SECONDS', 0.01), \
             patch('urllib.request.urlopen', lambda *a, **k: _Response(UP)):
            backend._watch_for_service()

        self.assertEqual(backend.mode, 'service')
        self.port.close.assert_called_once()
        self.assertIn('switched to it', self.sink.text())

    def test_watcher_stops_once_the_backend_is_cleaned_up(self):
        with patch('urllib.request.urlopen',
                   side_effect=urllib.error.URLError('down')), \
             patch.dict('sys.modules', {'serial': self.serial}):
            backend = _backend(self.sink)
        backend.cleanup()
        with patch.object(barrier_mod, 'REPROBE_SECONDS', 0.01), \
             patch('urllib.request.urlopen', lambda *a, **k: _Response(UP)):
            backend._watch_for_service()
        self.assertEqual(backend.mode, 'serial')

"""The UFD (customer-facing display) — what the driver at the barrier is told.

The display is optional hardware on a fire-and-forget HTTP GET, so a wrong URL
fails silently and nobody notices until a driver is shown the wrong balance.
These pin the URL each outcome produces.
"""

from unittest.mock import patch

from django.test import SimpleTestCase

from apps.tolls.management.commands import run_gate as run_gate_mod
from apps.tolls.management.commands.run_gate import GateController

DISPLAY_IP = '192.168.78.72'


class _Sink:
    def __init__(self):
        self.lines = []

    def write(self, msg):
        self.lines.append(msg)


class DisplayTestCase(SimpleTestCase):
    def setUp(self):
        self.urls = []
        # The barrier backend probes the network on construction; keep this a
        # pure unit test of the display by pinning it to the serial path with no
        # port present.
        patcher = patch.object(run_gate_mod, '_bg_display', self.urls.append)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.gate = GateController(
            gate_mode='entry', plaza_id=1, lane_id=1,
            serial_port='/dev/null', serial_baud=115200, open_secs=2.0,
            display_ip=DISPLAY_IP, tag_cooldown=5.0, stdout=_Sink(),
            barrier_mode='serial',
        )
        self.gate._running = False  # stop the portal-poll thread promptly

    def tearDown(self):
        self.gate._running = False


class EntryDisplayTests(DisplayTestCase):
    def test_entry_shows_the_remaining_balance(self):
        self.gate._show_entry('1234.56')
        self.assertEqual(
            self.urls,
            [f'http://{DISPLAY_IP}/?vehicle_number=R.BAL1234&fare_amount=0'],
        )

    def test_a_fractional_balance_is_truncated_not_rounded_up(self):
        """Showing more than the driver has would be a lie in their favour."""
        self.gate._show_balance('99.99')
        self.assertIn('R.BAL99', self.urls[0])

    def test_a_zero_balance_is_shown_as_zero(self):
        self.gate._show_balance('0')
        self.assertIn('R.BAL0', self.urls[0])

    def test_an_empty_balance_does_not_crash_the_display(self):
        self.gate._show_balance('')
        self.assertIn('R.BAL0', self.urls[0])


class ExitDisplayTests(DisplayTestCase):
    def test_exit_shows_the_fare_charged_and_what_is_left(self):
        self.gate._show_exit('100', '900')
        self.assertEqual(
            self.urls,
            [f'http://{DISPLAY_IP}/?vehicle_number=R.BAL900&fare_amount=100'],
        )

    def test_exit_to_a_zero_balance_still_reports_the_fare(self):
        self.gate._show_exit('100.00', '0.00')
        self.assertIn('R.BAL0', self.urls[0])
        self.assertIn('fare_amount=100.00', self.urls[0])


class DeniedDisplayTests(DisplayTestCase):
    def test_a_refusal_with_a_known_balance_shows_that_balance(self):
        """The balance is what explains the barrier and what to do about it."""
        self.gate._show_denied('ABC123', '10.00')
        self.assertEqual(len(self.urls), 1)
        self.assertIn('R.BAL10', self.urls[0])

    def test_a_refusal_with_no_account_leaves_the_display_alone(self):
        """Asserting a balance of 0 for an account that does not exist is a lie."""
        self.gate._show_denied('ABC123', None)
        self.assertEqual(self.urls, [])

    def test_low_balance_refusal_shows_the_shortfall_balance(self):
        self.gate._show_low_balance('25.00')
        self.assertIn('R.BAL25', self.urls[0])


class DisplayTransportTests(SimpleTestCase):
    """The display must never be able to hold up a lane."""

    def test_an_unreachable_display_is_swallowed(self):
        import requests
        with patch.object(requests, 'get', side_effect=OSError('no route')):
            run_gate_mod._fire('http://192.0.2.1/?x=1')  # must not raise

    def test_a_display_timeout_is_swallowed(self):
        import requests
        with patch.object(requests, 'get', side_effect=requests.Timeout('slow')):
            run_gate_mod._fire('http://192.0.2.1/?x=1')

    def test_the_get_carries_a_short_timeout(self):
        """Without one, a wedged display would pin a thread indefinitely."""
        import requests
        with patch.object(requests, 'get') as get:
            run_gate_mod._fire('http://192.0.2.1/?x=1')
        self.assertLessEqual(get.call_args.kwargs.get('timeout', 999), 5)

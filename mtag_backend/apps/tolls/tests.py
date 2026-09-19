from django.test import SimpleTestCase

from apps.tolls.management.commands.run_gate import GateController


def _gate(detect=0.0, open_min=0.0, open_max=0.0, window=5, hysteresis=3.0):
    """A GateController with only its RSSI state wired up.

    __init__ opens a serial port and starts the portal-polling thread, neither
    of which an RSSI decision test should drag in.
    """
    import threading

    gate = GateController.__new__(GateController)
    gate.rssi_detect = detect
    gate.rssi_open_min = open_min
    gate.rssi_open_max = open_max
    gate.rssi_window = window
    gate.rssi_hysteresis = hysteresis
    gate.tag_cooldown = 5.0
    gate._rssi_hist = {}
    gate._rssi_at_barrier = {}
    gate._rssi_stage_last = {}
    gate._balance_shown = {}
    gate._rssi_seen = {}
    gate._rssi_lock = threading.Lock()
    gate._rssi_pruned = 0.0

    class _Sink:
        def __init__(self):
            self.lines = []

        def write(self, msg):
            self.lines.append(msg)

    gate.stdout = _Sink()
    return gate


# A real trace captured from a stationary vehicle at an entry gate. The tag
# never moved; the spread is multipath, frequency hopping and the SDK's coarse
# RSSI quantisation.
STATIONARY_TRACE = [-52.6, -53.3, -52.0, -50.8, -49.8, -49.8, -50.8, -52.6]

# The band from the four-vehicle convoy test: detect far out, open at the boom.
DETECT, OPEN_MIN, OPEN_MAX = -70.0, -55.0, -52.0


def _stages(gate, tid, reads):
    return [gate._rssi_stage(tid, r) for r in reads]


def _transitions(seq):
    return sum(1 for a, b in zip(seq, seq[1:]) if a != b)


class RssiStagingTests(SimpleTestCase):
    """Three thresholds, two stages: show a balance far out, open at the boom."""

    def test_all_thresholds_off_opens_on_every_read(self):
        """The shipped config has all three at 0 — nothing is staged."""
        gate = _gate()
        self.assertTrue(
            all(s == 'open' for s in _stages(gate, 'T', STATIONARY_TRACE + [-99.0]))
        )

    def test_detect_threshold_alone_behaves_like_the_old_single_filter(self):
        """A booth that only sets a lower bound keeps its old behaviour."""
        gate = _gate(detect=-55.0)
        self.assertEqual(gate._rssi_stage('NEAR', -50.0), 'open')
        self.assertEqual(gate._rssi_stage('FAR', -70.0), 'ignore')

    def test_the_three_stages_are_separated_by_distance(self):
        gate = _gate(DETECT, OPEN_MIN, OPEN_MAX)
        # Beyond the reader's useful range for this lane.
        self.assertEqual(gate._rssi_stage('AWAY', -85.0), 'ignore')
        # In range: balance goes on the UFD, nothing is charged.
        self.assertEqual(gate._rssi_stage('APPROACH', -62.0), 'detect')
        # In the band: this is the arrival that opens the barrier.
        self.assertEqual(gate._rssi_stage('ARRIVED', -53.5), 'open')

    def test_a_tag_closer_than_the_band_does_not_open(self):
        """rssi_open_max is an upper bound, so an over-strong read is not an
        arrival — it is a tag sat on the reader, or in the wrong place."""
        gate = _gate(DETECT, OPEN_MIN, OPEN_MAX)
        self.assertEqual(
            _stages(gate, 'ONTOP', [-40.0, -41.0, -40.5]), ['detect'] * 3)

    def test_charging_stage_does_not_flap_for_a_stationary_vehicle(self):
        """The band sits mid-jitter on this real trace. Flapping here would
        charge a parked car twice, or drop the boom on it."""
        gate = _gate(DETECT, OPEN_MIN, OPEN_MAX)
        stages = _stages(gate, 'T', STATIONARY_TRACE)
        raw = ['open' if OPEN_MIN <= r <= OPEN_MAX else 'detect'
               for r in STATIONARY_TRACE]
        self.assertGreaterEqual(_transitions(raw), 2)
        self.assertLessEqual(_transitions(stages), 1)

    def test_single_outlier_does_not_release_a_tag_at_the_barrier(self):
        """One bad read must not retire a vehicle still in front of the boom."""
        gate = _gate(DETECT, OPEN_MIN, OPEN_MAX)
        _stages(gate, 'T', [-53.0, -53.0, -53.0])
        self.assertEqual(gate._rssi_stage('T', -70.0), 'open')

    def test_first_read_decides_immediately(self):
        """Smoothing must cost no gate latency — one sample is enough."""
        self.assertEqual(
            _gate(DETECT, OPEN_MIN, OPEN_MAX)._rssi_stage('A', -53.0), 'open')
        self.assertEqual(
            _gate(DETECT, OPEN_MIN, OPEN_MAX)._rssi_stage('B', -62.0), 'detect')

    def test_hysteresis_holds_a_tag_just_outside_the_band(self):
        gate = _gate(DETECT, OPEN_MIN, OPEN_MAX, hysteresis=3.0)
        _stages(gate, 'T', [-54.0] * 5)
        # Inside the hysteresis skirt: still treated as at the barrier.
        self.assertEqual(_stages(gate, 'T', [-57.0] * 5), ['open'] * 5)
        # Clear of it: let go.
        self.assertEqual(_stages(gate, 'T', [-62.0] * 5)[-1], 'detect')

    def test_newcomer_gets_no_hysteresis_slack(self):
        """Slack widens the band only for a tag already at the barrier."""
        gate = _gate(DETECT, OPEN_MIN, OPEN_MAX, hysteresis=3.0)
        self.assertEqual(_stages(gate, 'NEW', [-57.0] * 5), ['detect'] * 5)

    def test_stage_is_logged_once_per_change(self):
        """A car waiting in range must not emit one line per read."""
        gate = _gate(DETECT, OPEN_MIN, OPEN_MAX)
        _stages(gate, 'WAIT', [-62.0] * 8)
        self.assertEqual(len(gate.stdout.lines), 1, gate.stdout.lines)

    def test_window_is_bounded_and_stale_tags_are_pruned(self):
        gate = _gate(DETECT, OPEN_MIN, OPEN_MAX, window=5)
        _stages(gate, 'T', [-53.0] * 50)
        self.assertEqual(len(gate._rssi_hist['T']), 5)

        import time

        gate._rssi_pruned = time.monotonic() - 31.0
        gate._rssi_seen['T'] = time.monotonic() - 10_000.0
        gate._rssi_stage('OTHER', -53.0)
        self.assertNotIn('T', gate._rssi_hist)
        self.assertNotIn('T', gate._rssi_at_barrier)
        self.assertNotIn('T', gate._rssi_stage_last)
        self.assertIn('OTHER', gate._rssi_hist)

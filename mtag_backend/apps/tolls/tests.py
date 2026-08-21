from django.test import SimpleTestCase

from apps.tolls.management.commands.run_gate import GateController


def _gate(rssi_filter=0.0, rssi_filter_max=0.0, window=5, hysteresis=3.0):
    """A GateController with only its RSSI state wired up.

    __init__ opens a serial port and starts the portal-polling thread, neither
    of which an RSSI decision test should drag in.
    """
    import threading

    gate = GateController.__new__(GateController)
    gate.rssi_filter = rssi_filter
    gate.rssi_filter_max = rssi_filter_max
    gate.rssi_window = window
    gate.rssi_hysteresis = hysteresis
    gate.tag_cooldown = 5.0
    gate._rssi_hist = {}
    gate._rssi_pass = {}
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


def _verdicts(gate, tid, reads):
    return [gate._rssi_accepts(tid, r) for r in reads]


def _transitions(verdicts):
    return sum(1 for a, b in zip(verdicts, verdicts[1:]) if a != b)


class RssiFilterTests(SimpleTestCase):
    def test_disabled_filter_accepts_everything(self):
        """The shipped config has both thresholds at 0 — nothing is filtered."""
        gate = _gate(0.0, 0.0)
        self.assertTrue(all(_verdicts(gate, 'T', STATIONARY_TRACE + [-99.0])))

    def test_stationary_tag_does_not_flap(self):
        """A threshold parked mid-jitter must not toggle the verdict per read."""
        gate = _gate(rssi_filter=-52.0)
        verdicts = _verdicts(gate, 'T', STATIONARY_TRACE)
        # Raw single-read comparison flips twice on this exact trace.
        raw = [r >= -52.0 for r in STATIONARY_TRACE]
        self.assertEqual(_transitions(raw), 2)
        self.assertLessEqual(_transitions(verdicts), 1)
        self.assertTrue(verdicts[-1], "tag still in the field must stay accepted")

    def test_single_outlier_does_not_drop_an_accepted_tag(self):
        """One bad read among good ones must not evict a tag mid-pass."""
        gate = _gate(rssi_filter=-55.0)
        _verdicts(gate, 'T', [-50.0, -50.0, -50.0])
        self.assertTrue(gate._rssi_accepts('T', -70.0))

    def test_weak_tag_is_still_rejected(self):
        """Smoothing must not rescue a tag genuinely outside the lane."""
        gate = _gate(rssi_filter=-55.0)
        self.assertFalse(any(_verdicts(gate, 'FAR', [-60.9, -59.3, -58.6, -59.3])))

    def test_upper_bound_rejects_too_close_tags(self):
        gate = _gate(rssi_filter_max=-55.0)
        self.assertFalse(any(_verdicts(gate, 'NEAR', [-40.0, -41.0, -40.5])))

    def test_first_read_decides_immediately(self):
        """Smoothing must cost no gate latency — one sample is enough."""
        self.assertTrue(_gate(rssi_filter=-55.0)._rssi_accepts('A', -50.0))
        self.assertFalse(_gate(rssi_filter=-55.0)._rssi_accepts('B', -70.0))

    def test_hysteresis_holds_a_tag_just_below_the_threshold(self):
        """Once in, a tag needs to fall clear of the band before it is dropped."""
        gate = _gate(rssi_filter=-55.0, hysteresis=3.0)
        _verdicts(gate, 'T', [-54.0] * 5)
        # Inside the hysteresis band: still accepted.
        self.assertTrue(all(_verdicts(gate, 'T', [-57.0] * 5)))
        # Clear of it: dropped.
        self.assertFalse(all(_verdicts(gate, 'T', [-62.0] * 5)))

    def test_newcomer_gets_no_hysteresis_slack(self):
        """Hysteresis widens the band only for a tag already accepted."""
        gate = _gate(rssi_filter=-55.0, hysteresis=3.0)
        self.assertFalse(any(_verdicts(gate, 'NEW', [-57.0] * 5)))

    def test_ignored_is_logged_once_per_verdict_change(self):
        """A parked car must not emit one IGNORED line per read."""
        gate = _gate(rssi_filter=-55.0)
        _verdicts(gate, 'FAR', [-70.0] * 8)
        ignored = [ln for ln in gate.stdout.lines if 'IGNORED' in ln]
        self.assertEqual(len(ignored), 1, gate.stdout.lines)

    def test_window_is_bounded_and_stale_tags_are_pruned(self):
        gate = _gate(rssi_filter=-55.0, window=5)
        _verdicts(gate, 'T', [-50.0] * 50)
        self.assertEqual(len(gate._rssi_hist['T']), 5)

        import time

        gate._rssi_pruned = time.monotonic() - 31.0
        gate._rssi_seen['T'] = time.monotonic() - 10_000.0
        gate._rssi_accepts('OTHER', -50.0)
        self.assertNotIn('T', gate._rssi_hist)
        self.assertNotIn('T', gate._rssi_pass)
        self.assertIn('OTHER', gate._rssi_hist)

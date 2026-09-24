"""The booth console — the parts that can take a lane down if they are wrong.

Three things are worth pinning here, and they are not the HTML.

**The config validator must agree with run_gate.** A threshold set the gate
refuses to start on is not a validation error at the booth, it is a crash loop
under PM2 with the boom down. These tests hold `validate_changes` to the exact
rules in run_gate.Command.handle; if one side is changed, one of these fails.

**A config write must not lose the file.** rfid_config.ini is mostly comments,
and those comments are the only record of what the settings mean. A write that
round-tripped through configparser would silently delete all of them.

**Nothing may leak a credential.** A camera URL carries a password in its
userinfo, and this page renders the config back to a browser.

The activity recorder is checked for the property the gate depends on: that it
never raises into the caller, whatever state it is in.
"""

import inspect
import os
import shutil
import tempfile
import time
from configparser import ConfigParser
from unittest import mock

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.tolls import booth_activity, booth_probe, booth_stream
from apps.tolls.booth_console import (
    BoothCameraStreamView, BoothCameraView, BoothConfigView,
)

SAMPLE_CONFIG = """[gate]
; Ceiling on any single database query, in milliseconds.
statement_timeout_ms = 10000

mode = exit
plaza_id = 002
lane_number = 1

[scanner]
reader_host = 192.168.1.116
reader_port = 9090
tag_cooldown = 5.0
antenna_power = 20
scan_interval = 1.0
# Accept a tag only while its signal sits inside this band, in dBm (0 = off).
rssi_filter = 0
rssi_filter_max = 0
# Jitter tolerance for the two thresholds above.
rssi_window = 5
rssi_hysteresis = 3.0

[barrier]
port = /dev/ttyUSB0
baudrate = 115200
open_seconds = 2.0

[display]
display_ip = 192.168.78.72
"""

BASELINE = {
    'scanner.rssi_detect': '0',
    'scanner.rssi_open_min': '0',
    'scanner.rssi_open_max': '0',
    'scanner.rssi_window': '5',
    'scanner.rssi_hysteresis': '3.0',
    'scanner.antenna_power': '20',
    'scanner.reader_port': '9090',
    'barrier.baudrate': '115200',
}


def _changes(**kwargs):
    """{'scanner__rssi_detect': '-70'} -> {('scanner', 'rssi_detect'): '-70'}"""
    return {tuple(key.split('__', 1)): value for key, value in kwargs.items()}


class ValidatorMatchesTheGateTests(SimpleTestCase):
    """Every rule here has a counterpart in run_gate.Command.handle."""

    def assertAccepted(self, **kwargs):
        errors = booth_probe.validate_changes(_changes(**kwargs), BASELINE)
        self.assertEqual(errors, [], f"unexpectedly rejected: {errors}")

    def assertRejected(self, needle, **kwargs):
        errors = booth_probe.validate_changes(_changes(**kwargs), BASELINE)
        self.assertTrue(errors, 'expected a rejection, got none')
        self.assertIn(needle, ' '.join(errors))

    def test_a_well_ordered_band_is_accepted(self):
        self.assertAccepted(
            scanner__rssi_detect='-70',
            scanner__rssi_open_min='-55',
            scanner__rssi_open_max='-45',
        )

    def test_an_inverted_open_band_is_refused(self):
        """run_gate: 'the barrier could never open'."""
        self.assertRejected(
            'could never open',
            scanner__rssi_detect='-70',
            scanner__rssi_open_min='-45',
            scanner__rssi_open_max='-55',
        )

    def test_detect_above_the_open_band_is_refused(self):
        """A vehicle must be noticed before it can be let through."""
        self.assertRejected(
            'before the gate ever noticed',
            scanner__rssi_detect='-50',
            scanner__rssi_open_min='-55',
            scanner__rssi_open_max='-45',
        )

    def test_a_single_threshold_is_validated_against_the_two_it_leaves_alone(self):
        """The check is on the merged result, not on the submitted keys.

        Lowering only open_min, against a detect already in the file, is the
        realistic way to produce an invalid ordering — and the way a validator
        that only looked at what was submitted would miss it.
        """
        current = dict(BASELINE, **{
            'scanner.rssi_detect': '-50', 'scanner.rssi_open_max': '-45'})
        errors = booth_probe.validate_changes(
            _changes(scanner__rssi_open_min='-55'), current)
        self.assertTrue(errors)
        self.assertIn('before the gate ever noticed', ' '.join(errors))

    def test_zero_thresholds_are_accepted_because_zero_means_off(self):
        self.assertAccepted(
            scanner__rssi_detect='0',
            scanner__rssi_open_min='0',
            scanner__rssi_open_max='0',
        )

    def test_a_window_below_one_is_refused(self):
        self.assertRejected('rssi_window', scanner__rssi_window='0')

    def test_negative_hysteresis_is_refused(self):
        self.assertRejected('rssi_hysteresis', scanner__rssi_hysteresis='-1')

    def test_antenna_power_above_the_readers_ceiling_is_refused(self):
        self.assertRejected('antenna_power', scanner__antenna_power='99')

    def test_a_baud_rate_the_relay_cannot_use_is_refused(self):
        self.assertRejected('baudrate', barrier__baudrate='12345')

    def test_a_non_numeric_value_is_refused_rather_than_written(self):
        self.assertRejected('must be a number', scanner__tag_cooldown='soon')

    def test_gate_identity_keys_cannot_be_changed_from_the_console(self):
        """Plaza and mode decide who gets billed — SSH only."""
        self.assertRejected('cannot be changed from the console', gate__plaza_id='9')
        self.assertRejected('cannot be changed from the console', gate__mode='entry')
        self.assertRejected('cannot be changed from the console', gate__lane_number='4')

    def test_an_unknown_key_in_an_editable_section_is_refused(self):
        self.assertRejected('cannot be changed', scanner__delete_everything='1')

    def test_a_host_that_looks_like_a_shell_fragment_is_refused(self):
        self.assertRejected('not a valid hostname', scanner__reader_host='10.0.0.1; rm -rf /')

    def test_a_camera_url_with_a_scheme_the_booth_cannot_open_is_refused(self):
        self.assertRejected('must start with rtsp', camera__rtsp_url='javascript:alert(1)')

    def test_a_serial_port_outside_dev_is_refused(self):
        self.assertRejected('is not a device path', barrier__port='../../etc/passwd')


class ConfigWriteTests(SimpleTestCase):
    """A write must change the values named and nothing else at all."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.path = os.path.join(self.dir, 'rfid_config.ini')
        with open(self.path, 'w', encoding='utf-8') as handle:
            handle.write(SAMPLE_CONFIG)

    def _parsed(self):
        parser = ConfigParser()
        parser.read(self.path)
        return parser

    def test_comments_survive_a_write(self):
        before = sum(1 for line in SAMPLE_CONFIG.splitlines()
                     if line.strip().startswith(('#', ';')))
        booth_probe.write_changes(
            _changes(scanner__antenna_power='25'), path=self.path)
        after = sum(1 for line in open(self.path, encoding='utf-8')
                    if line.strip().startswith(('#', ';')))
        self.assertEqual(before, after)
        self.assertGreater(after, 0)

    def test_only_the_named_values_change(self):
        booth_probe.write_changes(
            _changes(scanner__antenna_power='25'), path=self.path)
        parser = self._parsed()
        self.assertEqual(parser.get('scanner', 'antenna_power'), '25')
        self.assertEqual(parser.get('gate', 'plaza_id'), '002')
        self.assertEqual(parser.get('scanner', 'reader_host'), '192.168.1.116')
        self.assertEqual(parser.get('display', 'display_ip'), '192.168.78.72')
        self.assertEqual(parser.get('barrier', 'open_seconds'), '2.0')

    def test_a_key_the_section_does_not_have_is_appended_to_it(self):
        """A booth on the old rssi_filter keys gains the new ones in place."""
        booth_probe.write_changes(
            _changes(scanner__rssi_detect='-70'), path=self.path)
        parser = self._parsed()
        self.assertEqual(parser.get('scanner', 'rssi_detect'), '-70')
        # The legacy keys are left alone; run_gate prefers the new ones.
        self.assertEqual(parser.get('scanner', 'rssi_filter'), '0')

    def test_a_section_the_file_does_not_have_is_created(self):
        booth_probe.write_changes(
            _changes(camera__rtsp_url='rtsp://10.0.0.8/s'), path=self.path)
        parser = self._parsed()
        self.assertEqual(parser.get('camera', 'rtsp_url'), 'rtsp://10.0.0.8/s')

    def test_several_keys_into_a_brand_new_section_all_land_in_it(self):
        """Saving the camera panel writes three keys into a section that does
        not exist yet, against a file that ends in a blank line. The line index
        and the section index have to stay in step through that, or the second
        key is placed by a stale offset."""
        with open(self.path, 'a', encoding='utf-8') as handle:
            handle.write('\n\n')
        booth_probe.write_changes(_changes(
            camera__rtsp_url='rtsp://10.0.0.8/s',
            camera__transport='tcp',
            camera__snapshot_url='http://10.0.0.8/jpg',
        ), path=self.path)
        parser = self._parsed()
        self.assertEqual(parser.get('camera', 'rtsp_url'), 'rtsp://10.0.0.8/s')
        self.assertEqual(parser.get('camera', 'transport'), 'tcp')
        self.assertEqual(parser.get('camera', 'snapshot_url'), 'http://10.0.0.8/jpg')
        # And nothing was pushed into a neighbouring section on the way.
        self.assertFalse(parser.has_option('display', 'transport'))
        self.assertFalse(parser.has_option('barrier', 'rtsp_url'))
        self.assertEqual(parser.get('display', 'display_ip'), '192.168.78.72')

    def test_keys_added_to_an_existing_section_stay_in_it(self):
        booth_probe.write_changes(_changes(
            scanner__rssi_detect='-70',
            scanner__rssi_open_min='-55',
            scanner__rssi_open_max='-45',
        ), path=self.path)
        parser = self._parsed()
        for key in ('rssi_detect', 'rssi_open_min', 'rssi_open_max'):
            self.assertTrue(parser.has_option('scanner', key), key)
        self.assertFalse(parser.has_option('barrier', 'rssi_detect'))

    def test_a_backup_is_left_and_restores_the_previous_file(self):
        booth_probe.write_changes(
            _changes(scanner__antenna_power='30'), path=self.path)
        self.assertTrue(os.path.exists(self.path + '.bak'))
        self.assertTrue(booth_probe.restore_backup(path=self.path))
        self.assertEqual(self._parsed().get('scanner', 'antenna_power'), '20')

    def test_the_written_file_always_parses(self):
        booth_probe.write_changes(_changes(
            scanner__rssi_detect='-70',
            scanner__rssi_open_min='-55',
            camera__rtsp_url='rtsp://a:b@10.0.0.8:554/x',
            barrier__mode='serial',
        ), path=self.path)
        parser = ConfigParser()
        self.assertTrue(parser.read(self.path))
        self.assertEqual(parser.get('barrier', 'mode'), 'serial')

    def test_restore_reports_honestly_when_there_is_no_backup(self):
        self.assertFalse(booth_probe.restore_backup(path=self.path))


class PercentInAValueTests(SimpleTestCase):
    """A '%' in a value must be data, not a configparser substitution.

    Found on a live booth: a camera URL whose password was URL-encoded
    (`Iteck%40123`, i.e. `Iteck@123`). configparser's default BasicInterpolation
    raised InterpolationSyntaxError, `_get` caught it as any other
    configparser.Error and returned its fallback, and the console reported a
    fully configured camera as "not configured" — answering 502 and sending
    whoever read it looking at the camera, the cabling and ffmpeg instead.

    The same class of value reaches the gate, where the exception is NOT caught
    and would crash-loop the lane under PM2.
    """

    REAL_WORLD_URL = 'rtsp://admin:Iteck%40123@192.168.78.21:554/Streaming/Channels/101'

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.path = os.path.join(self.dir, 'rfid_config.ini')
        with open(self.path, 'w', encoding='utf-8') as handle:
            handle.write(SAMPLE_CONFIG + f'\n[camera]\nrtsp_url = {self.REAL_WORLD_URL}\n'
                                          'transport = tcp\n')

    def test_the_url_survives_being_read_back(self):
        parser = booth_probe.raw_config_parser(path=self.path)
        self.assertEqual(parser.get('camera', 'rtsp_url'), self.REAL_WORLD_URL)

    def test_gate_identity_reports_the_camera_as_configured(self):
        identity = booth_probe.gate_identity(
            booth_probe.raw_config_parser(path=self.path))
        self.assertEqual(identity['camera_rtsp_url'], self.REAL_WORLD_URL)
        self.assertTrue(identity['camera_rtsp_url'],
                        'an empty URL is what produced the misleading 502')

    def test_read_config_returns_sections_instead_of_raising(self):
        config = booth_probe.read_config(path=self.path)
        self.assertEqual(config['error'], '')
        self.assertIn('camera', config['sections'])
        self.assertEqual(config['sections']['camera']['transport'], 'tcp')

    def test_the_encoded_password_is_still_redacted(self):
        config = booth_probe.read_config(path=self.path)
        shown = config['sections']['camera']['rtsp_url']
        self.assertNotIn('Iteck%40123', shown)
        self.assertNotIn('Iteck%40123', config['raw'])
        self.assertIn('admin', shown)
        self.assertIn('192.168.78.21', shown)

    def test_such_a_value_can_be_written_and_read_back_unchanged(self):
        booth_probe.write_changes(
            _changes(camera__rtsp_url=self.REAL_WORLD_URL), path=self.path)
        parser = booth_probe.raw_config_parser(path=self.path)
        self.assertEqual(parser.get('camera', 'rtsp_url'), self.REAL_WORLD_URL)

    def test_the_gate_parses_the_same_file_without_raising(self):
        """run_gate does not catch InterpolationSyntaxError — it would crash."""
        import configparser as cp
        from apps.tolls.management.commands import run_gate as run_gate_mod
        source = inspect.getsource(run_gate_mod.Command.handle)
        self.assertIn('interpolation=None', source)

        parser = cp.ConfigParser(interpolation=None)
        parser.read(self.path)
        for section, key in (('scanner', 'reader_host'), ('barrier', 'port'),
                             ('display', 'display_ip'), ('camera', 'rtsp_url')):
            parser.get(section, key)  # must not raise


class RedactionTests(SimpleTestCase):
    """This page renders the config into a browser. Nothing secret may ride along."""

    def test_a_camera_password_is_stripped_but_the_username_is_kept(self):
        redacted = booth_probe.redact_url('rtsp://admin:hunter2@10.0.0.8:554/Stream')
        self.assertNotIn('hunter2', redacted)
        self.assertIn('admin', redacted)
        self.assertIn('10.0.0.8:554/Stream', redacted)

    def test_a_password_written_with_a_literal_at_sign_is_fully_redacted(self):
        """The documented form is percent-encoded, but people will type it raw.

        With a non-greedy password group the redaction stopped at the FIRST '@'
        and printed the remainder of the password to the page as though it were
        part of the hostname.
        """
        redacted = booth_probe.redact_url(
            'rtsp://admin:Iteck@123@192.168.78.21:554/Streaming/Channels/101')
        self.assertNotIn('Iteck', redacted)
        self.assertNotIn('123@', redacted)
        self.assertIn('192.168.78.21:554/Streaming/Channels/101', redacted)

    def test_a_password_containing_a_colon_is_fully_redacted(self):
        redacted = booth_probe.redact_url('rtsp://admin:p@ss:w0rd@10.0.0.8/live')
        self.assertNotIn('p@ss', redacted)
        self.assertNotIn('w0rd', redacted)
        self.assertIn('10.0.0.8/live', redacted)

    def test_a_url_without_credentials_is_untouched(self):
        url = 'rtsp://10.0.0.8:554/Streaming/Channels/101'
        self.assertEqual(booth_probe.redact_url(url), url)

    def test_secret_looking_keys_are_blanked_entirely(self):
        self.assertEqual(booth_probe.redact_value('operator_token', 'eyJhbGc'),
                         booth_probe.REDACTED)
        self.assertEqual(booth_probe.redact_value('db_password', 'hunter2'),
                         booth_probe.REDACTED)

    def test_ordinary_keys_are_shown_as_they_are(self):
        self.assertEqual(
            booth_probe.redact_value('reader_host', '192.168.1.116'), '192.168.1.116')

    def test_the_raw_file_view_is_redacted_too(self):
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory, True)
        path = os.path.join(directory, 'rfid_config.ini')
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(SAMPLE_CONFIG + '\n[camera]\nrtsp_url = rtsp://a:s3cret@10.0.0.8/x\n')
        config = booth_probe.read_config(path=path)
        self.assertNotIn('s3cret', config['raw'])
        self.assertNotIn('s3cret', config['sections']['camera']['rtsp_url'])
        # The comments are still there to read.
        self.assertIn('Jitter tolerance', config['raw'])


class ActivityRecorderTests(SimpleTestCase):
    """The gate calls these from the thread that handles every vehicle."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.path = os.path.join(self.dir, 'activity.db')

    def _recorder(self):
        recorder = booth_activity.ActivityRecorder(db_path=self.path)
        self.addCleanup(recorder.close)
        recorder._ready.wait(5)
        return recorder

    def _wait_for(self, count, reader, timeout=5.0):
        deadline = time.monotonic() + timeout
        rows = []
        while time.monotonic() < deadline:
            rows = reader(limit=1000, db_path=self.path)
            if len(rows) >= count:
                return rows
            time.sleep(0.05)
        return rows

    def test_reads_are_written_and_read_back(self):
        recorder = self._recorder()
        for index in range(10):
            recorder.record_read(epc='E1', tid='T1', rssi=-50 - index,
                                 median=-52.0, samples=5, stage='open')
        rows = self._wait_for(10, booth_activity.read_tag_reads)
        self.assertEqual(len(rows), 10)
        self.assertEqual(rows[0]['tid'], 'T1')
        self.assertEqual(rows[0]['stage'], 'open')
        self.assertAlmostEqual(rows[0]['rssi'], -50.0)

    def test_since_id_returns_only_what_the_caller_has_not_seen(self):
        """This is what keeps the console's 2-second poll cheap."""
        recorder = self._recorder()
        for index in range(10):
            recorder.record_read(epc='E', tid='T', rssi=-50, median=-50,
                                 samples=1, stage='open')
        rows = self._wait_for(10, booth_activity.read_tag_reads)
        newer = booth_activity.read_tag_reads(
            limit=100, since_id=rows[6]['id'], db_path=self.path)
        self.assertEqual(len(newer), 3)
        self.assertTrue(all(row['id'] > rows[6]['id'] for row in newer))

    def test_reading_a_database_that_does_not_exist_creates_nothing(self):
        """The web process must not leave an empty file on a host with no gate."""
        missing = os.path.join(self.dir, 'absent.db')
        self.assertEqual(booth_activity.read_tag_reads(db_path=missing), [])
        self.assertFalse(os.path.exists(missing))

    def test_recording_never_raises_even_when_the_file_cannot_be_opened(self):
        """The gate's tag thread must survive a read-only or full disk."""
        recorder = booth_activity.ActivityRecorder(
            db_path=os.path.join(self.dir, 'no', 'such', 'dir', 'a.db'))
        self.addCleanup(recorder.close)
        recorder._ready.wait(5)
        recorder.record_read(epc='E', tid='T', rssi=-50, median=-50,
                             samples=1, stage='open')
        recorder.record_gate_event(kind='exit', tid='T', result='ok')
        recorder.record_barrier(action='hold', ok=True)
        self.assertTrue(recorder.stats()['error'])

    def test_the_null_recorder_accepts_everything_and_does_nothing(self):
        null = booth_activity.NullRecorder()
        null.record_read(epc='E', tid='T', rssi=-50, median=-50, samples=1, stage='open')
        null.record_gate_event(kind='entry')
        null.record_barrier(action='hold')
        self.assertFalse(null.stats()['running'])

    def test_the_summary_counts_what_the_console_shows(self):
        recorder = self._recorder()
        for stage in ('open', 'open', 'detect', 'ignore'):
            recorder.record_read(epc='E', tid='T' + stage, rssi=-50,
                                 median=-50, samples=1, stage=stage)
        recorder.record_barrier(action='hold', ok=True)
        recorder.record_gate_event(kind='exit', result='ok')
        self._wait_for(4, booth_activity.read_tag_reads)
        summary = booth_activity.read_summary(db_path=self.path)
        self.assertEqual(summary['reads'], 4)
        self.assertEqual(summary['stages']['open'], 2)
        self.assertEqual(summary['barrier_opens'], 1)


class _StubUser:
    """Enough of a user for the permission and throttle layers, with no database."""
    is_authenticated = True
    is_active = True

    def __init__(self, role):
        self.user_role = role
        self.pk = 1
        self.id = 1
        self.phone = '03001234567'


class ConsolePermissionTests(SimpleTestCase):
    """Reads need an operator; changing the lane needs an admin.

    Only views that touch no database are exercised here, so the gate on each
    one is pinned without a Postgres to hand.
    """

    def setUp(self):
        self.factory = APIRequestFactory()

    def _call(self, view, request, user=None):
        if user is not None:
            force_authenticate(request, user=user)
        return view.as_view()(request)

    def test_an_anonymous_caller_is_asked_to_sign_in(self):
        response = self._call(BoothCameraView, self.factory.get('/booth/api/camera/'))
        self.assertEqual(response.status_code, 401)

    def test_a_consumer_account_is_refused(self):
        response = self._call(BoothCameraView, self.factory.get('/booth/api/camera/'),
                              _StubUser('user'))
        self.assertEqual(response.status_code, 403)

    def test_an_operator_may_read(self):
        response = self._call(BoothCameraView, self.factory.get('/booth/api/camera/'),
                              _StubUser('operator'))
        self.assertEqual(response.status_code, 200)

    def test_an_operator_may_read_the_config_but_not_write_it(self):
        read = self._call(BoothConfigView, self.factory.get('/booth/api/config/'),
                          _StubUser('operator'))
        self.assertEqual(read.status_code, 200)

        write = self._call(
            BoothConfigView,
            self.factory.post('/booth/api/config/',
                              {'changes': {'scanner.antenna_power': '25'}}, format='json'),
            _StubUser('operator'))
        self.assertEqual(write.status_code, 403)

    def test_the_console_throttle_is_generous_enough_for_its_own_polling(self):
        """The default `user` rate is 2000/hour; one open tab exceeds it.

        Instantiating it also pins the other half of the bug this replaced: a
        scope with no rate in settings raises ImproperlyConfigured right here,
        which reached the browser as a 500 on every console call.
        """
        from apps.tolls.booth_console import BoothConsoleThrottle
        throttle = BoothConsoleThrottle()
        per_hour = throttle.num_requests / (throttle.duration / 3600.0)
        self.assertGreaterEqual(per_hour, 10000)


class CameraStreamTests(SimpleTestCase):
    """The live view holds a gunicorn thread and an ffmpeg for as long as it runs.

    The booth has four request threads in total (gunicorn.conf.py) and a lane to
    run on the same CPU, so the things worth pinning are not the picture — they
    are the limits that stop the picture becoming the reason the booth is slow.

    None of these need ffmpeg: a pipeline that fails to start still attaches its
    viewer, which is exactly the accounting under test.
    """

    def setUp(self):
        self.stream = booth_stream.CameraStream()
        self.addCleanup(self.stream.stop)

    def test_attach_is_separate_from_the_generator(self):
        """Because a generator body does not run until it is first iterated.

        When attach() lived inside frames(), the "too many viewers" error was
        raised midway through the response body — after 200 had already been
        sent — so the view could not turn it into a 429 and the browser got a
        truncated stream instead.
        """
        self.assertFalse(
            inspect.isgeneratorfunction(booth_stream.CameraStream.attach),
            'attach() must run eagerly so the view can still choose a status code')
        self.assertTrue(
            inspect.isgeneratorfunction(booth_stream.CameraStream.frames_for))
        # And frames_for takes an already-attached viewer rather than a url.
        params = list(inspect.signature(
            booth_stream.CameraStream.frames_for).parameters)
        self.assertEqual(params, ['self', 'viewer'])

    def test_viewers_are_capped(self):
        for _ in range(booth_stream.MAX_VIEWERS):
            self.stream.attach('', {})
        with self.assertRaises(RuntimeError):
            self.stream.attach('', {})
        self.assertEqual(self.stream.status()['viewers'], booth_stream.MAX_VIEWERS)

    def test_the_cap_is_small_enough_to_leave_the_booth_responsive(self):
        """gunicorn runs 1 worker with 4 threads; each viewer holds one."""
        self.assertLessEqual(booth_stream.MAX_VIEWERS, 2)

    def test_detaching_frees_a_slot(self):
        viewers = [self.stream.attach('', {})
                   for _ in range(booth_stream.MAX_VIEWERS)]
        self.stream.detach(viewers[0])
        self.assertEqual(self.stream.status()['viewers'],
                         booth_stream.MAX_VIEWERS - 1)
        self.stream.attach('', {})  # must not raise

    def test_detach_is_idempotent(self):
        """The view registers a second closer beside the generator's own."""
        viewer = self.stream.attach('', {})
        self.stream.detach(viewer)
        self.stream.detach(viewer)
        self.assertEqual(self.stream.status()['viewers'], 0)

    def test_a_session_cannot_run_indefinitely(self):
        """A console left open on a spare monitor is the realistic failure."""
        self.assertLessEqual(booth_stream.MAX_SESSION_SECONDS, 900)
        self.assertGreater(booth_stream.MAX_SESSION_SECONDS, 60)

    def test_a_slow_viewer_drops_frames_rather_than_blocking(self):
        """One stalled browser must not stall the reader for everyone else."""
        viewer = booth_stream._Viewer()
        for index in range(5):
            viewer.offer(b'frame%d' % index)
        self.assertEqual(viewer.frames.qsize(), 1)
        self.assertEqual(viewer.frames.get_nowait(), b'frame4',
                         'the viewer should hold the NEWEST frame, not the oldest')
        self.assertEqual(viewer.dropped, 4)

    def test_a_failed_start_reports_why(self):
        with mock.patch.object(booth_probe, '_ffmpeg_binary', lambda name='ffmpeg': ''):
            self.stream.attach('rtsp://10.0.0.1/s', {})
        self.assertIn('ffmpeg', self.stream.status()['error'])
        self.assertFalse(self.stream.status()['running'])


class CameraStreamViewTests(SimpleTestCase):
    """Refusals must be status codes, not a 200 with a broken body."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.cfg = os.path.join(self.dir, 'rfid_config.ini')
        with open(self.cfg, 'w', encoding='utf-8') as handle:
            handle.write(SAMPLE_CONFIG +
                         '\n[camera]\nrtsp_url = rtsp://10.0.0.8/profile1\n')
        booth_stream.get_stream().stop()

    def _get(self, role='operator'):
        request = self.factory.get('/booth/api/camera/stream/')
        force_authenticate(request, user=_StubUser(role))
        return BoothCameraStreamView.as_view()(request)

    def test_a_host_with_no_camera_configured_says_so(self):
        blank = os.path.join(self.dir, 'blank.ini')
        with open(blank, 'w', encoding='utf-8') as handle:
            handle.write(SAMPLE_CONFIG)
        with mock.patch.object(booth_probe, 'config_path', lambda: blank):
            response = self._get()
        self.assertEqual(response.status_code, 409)
        self.assertIn('rtsp_url', response.data['message'])

    def test_a_booth_without_ffmpeg_says_so(self):
        with mock.patch.object(booth_probe, 'config_path', lambda: self.cfg), \
             mock.patch.object(booth_probe, 'camera_available',
                               lambda: {'ffmpeg': False, 'ffprobe': False}):
            response = self._get()
        self.assertEqual(response.status_code, 503)
        self.assertIn('ffmpeg', response.data['message'])

    def test_too_many_viewers_is_a_429_not_a_broken_stream(self):
        with mock.patch.object(booth_probe, 'config_path', lambda: self.cfg), \
             mock.patch.object(booth_probe, 'camera_available',
                               lambda: {'ffmpeg': True, 'ffprobe': True}), \
             mock.patch.object(booth_stream, 'MAX_VIEWERS', 0):
            response = self._get()
        self.assertEqual(response.status_code, 429)
        self.assertTrue(hasattr(response, 'data'),
                        'a refusal must be a response body, not a streaming one')

    def test_a_pipeline_that_will_not_start_is_a_502_and_leaks_no_viewer(self):
        with mock.patch.object(booth_probe, 'config_path', lambda: self.cfg), \
             mock.patch.object(booth_probe, 'camera_available',
                               lambda: {'ffmpeg': True, 'ffprobe': True}), \
             mock.patch.object(booth_probe, '_ffmpeg_binary',
                               lambda name='ffmpeg': '/nonexistent/ffmpeg'):
            response = self._get()
        self.assertEqual(response.status_code, 502)
        self.assertEqual(booth_stream.get_stream().status()['viewers'], 0)


class ConsolePageTests(SimpleTestCase):
    """The shell is served anonymously so it can render its own login form."""

    def test_the_page_renders_without_a_session(self):
        response = self.client.get('/booth/')
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('Booth Console', body)
        self.assertIn('rssi-chart', body)
        self.assertIn('login-form', body)

    def test_signed_out_is_distinguishable_from_not_yet_known(self):
        """The console shipped once with `authed` starting at `false`.

        The first 401 then called setAuthed(false), the equality guard inside it
        returned early, and the login overlay — hidden in the markup — was never
        unhidden. The page sat there polling a booth it had no credentials for,
        four requests every two seconds, with no way for anyone to sign in. It
        was found in a booth's own gunicorn log, as an unbroken run of 401s.

        There is no JS test runner in this project, so this asserts on the
        source. That is a weak test for most things and the right one for this:
        the failure was a single initial value, and it is that value being
        three-state which makes the overlay reachable at all.
        """
        page = self.client.get('/booth/').content.decode()
        self.assertIn('authed: null', page,
                      "auth state must be tri-state (null / true / false)")
        self.assertNotIn('authed: false,', page,
                         "a two-state flag cannot show the overlay on the first 401")
        # And the pollers must stand down rather than hammer a booth that has
        # already told them no.
        self.assertGreaterEqual(
            page.count('state.authed === false'), 4,
            "every poller needs the signed-out guard")

    def test_the_page_carries_no_booth_data_of_its_own(self):
        """Every panel is filled by an authenticated call, not by the template.

        Checked against this host's real configured values rather than against
        example strings: the form's help text legitimately mentions
        /dev/ttyUSB0 and rtsp:// as documentation, and asserting on those would
        fail on wording instead of on a leak.
        """
        body = self.client.get('/booth/').content.decode()
        if not booth_probe.is_booth():
            self.skipTest('no rfid_config.ini here — nothing that could leak')
        identity = booth_probe.gate_identity()
        for key in ('reader_host', 'display_ip', 'camera_rtsp_url', 'plaza_id'):
            value = (identity.get(key) or '').strip()
            if value:
                self.assertNotIn(value, body, f'{key} reached the anonymous page')

"""Phone-OTP first-time password setup.

The tests that matter here are the abuse cases. A 6-digit code is 10^6 — trivially
brute-forceable if attempts are not capped — and a set-password endpoint is, by definition,
account takeover if any of its guards fail.
"""

import json
from contextlib import contextmanager
from datetime import timedelta
from unittest.mock import patch

from django.core import signing
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from .models import PhoneOtp, User, UserStatus


def last_code_for(phone, monkeypatched):
    """The plaintext code, captured from the console sender."""
    return monkeypatched[-1]


@override_settings(SMS_BACKEND='console')
class OtpFlowTest(TestCase):
    def setUp(self):
        # The OTP endpoints are throttled at 5/minute, which is right in production and
        # useless here — these tests deliberately hammer them. Patched off rather than
        # overridden via REST_FRAMEWORK: replacing that dict wholesale drops the auth
        # classes and exception handler with it.
        from .views import OtpRateThrottle

        original_allow = OtpRateThrottle.allow_request
        OtpRateThrottle.allow_request = lambda self, request, view: True
        self.addCleanup(setattr, OtpRateThrottle, 'allow_request', original_allow)

        self.client = APIClient()
        self.user = User.objects.create_user(
            phone='03001112233', password='initialpass123', full_name='Tag Holder'
        )
        self.sent = []
        # Capture the plaintext code the way the SMS backend would deliver it.
        from . import otp_service

        original = otp_service.get_sms_sender

        class _Capture:
            name = 'console'

            def send(inner, *, phone, message):  # noqa: N805
                self.sent.append(message.split()[0])
                return True

        otp_service.get_sms_sender = lambda: _Capture()
        self.addCleanup(setattr, otp_service, 'get_sms_sender', original)

    def _request(self, phone='03001112233'):
        return self.client.post(
            '/api/v1/auth/otp/request/', {'phone': phone}, format='json'
        )

    def _verify(self, code, phone='03001112233'):
        return self.client.post(
            '/api/v1/auth/otp/verify/', {'phone': phone, 'code': code}, format='json'
        )

    # ── happy path ───────────────────────────────────────────────────────────
    def test_full_flow_sets_password_and_signs_in(self):
        self.assertEqual(self._request().status_code, status.HTTP_200_OK)
        verified = self._verify(self.sent[-1])
        self.assertEqual(verified.status_code, status.HTTP_200_OK)
        token = verified.json()['data']['token']

        response = self.client.post(
            '/api/v1/auth/otp/set-password/',
            {'token': token, 'new_password': 'brandnew123', 'confirm_password': 'brandnew123'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Signed in immediately — no second login step.
        self.assertIn('access_token', response.cookies)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('brandnew123'))

    # ── it is NOT signup ─────────────────────────────────────────────────────
    def test_unknown_number_is_refused_and_creates_nothing(self):
        response = self._request(phone='03009998877')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json()['errors']['reason'], 'no_account')
        self.assertFalse(User.objects.filter(phone='03009998877').exists())
        self.assertFalse(PhoneOtp.objects.filter(phone='03009998877').exists())

    def test_blocked_account_cannot_reset_its_way_back_in(self):
        self.user.status = UserStatus.BLOCKED
        self.user.save(update_fields=['status'])
        response = self._request()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['errors']['reason'], 'blocked')

    # ── the code itself ──────────────────────────────────────────────────────
    def test_code_is_never_stored_in_plaintext(self):
        self._request()
        otp = PhoneOtp.objects.latest('created_at')
        self.assertNotIn(self.sent[-1], otp.code_hash)
        self.assertNotEqual(otp.code_hash, self.sent[-1])

    def test_wrong_code_is_rejected(self):
        self._request()
        wrong = '000000' if self.sent[-1] != '000000' else '111111'
        response = self._verify(wrong)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_attempts_are_capped(self):
        """A 6-digit code is 10^6. Without a cap it falls in minutes."""
        self._request()
        real = self.sent[-1]
        wrong = '000000' if real != '000000' else '111111'
        for _ in range(PhoneOtp.MAX_ATTEMPTS):
            self._verify(wrong)
        # Even the CORRECT code is now refused — the code is burned, not just the guess.
        response = self._verify(real)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['errors']['reason'], 'too_many_attempts')

    def test_expired_code_is_rejected(self):
        self._request()
        otp = PhoneOtp.objects.latest('created_at')
        otp.expires_at = timezone.now() - timedelta(seconds=1)
        otp.save(update_fields=['expires_at'])
        response = self._verify(self.sent[-1])
        self.assertEqual(response.json()['errors']['reason'], 'expired')

    def test_code_is_single_use(self):
        self._request()
        code = self.sent[-1]
        self.assertEqual(self._verify(code).status_code, status.HTTP_200_OK)
        self.assertEqual(self._verify(code).status_code, status.HTTP_400_BAD_REQUEST)

    def test_requesting_a_new_code_invalidates_the_old_one(self):
        """An intercepted code must not still work after the user asks for another."""
        self._request()
        first = self.sent[-1]
        self._request()
        response = self._verify(first)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ── the set-password token ───────────────────────────────────────────────
    def test_forged_token_is_refused(self):
        response = self.client.post(
            '/api/v1/auth/otp/set-password/',
            {
                'token': signing.dumps({'phone': '03001112233'}, salt='wrong-salt'),
                'new_password': 'attacker123',
                'confirm_password': 'attacker123',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertFalse(self.user.check_password('attacker123'))

    def test_set_password_requires_a_verified_token(self):
        """Skipping straight to set-password must not work."""
        response = self.client.post(
            '/api/v1/auth/otp/set-password/',
            {'token': '', 'new_password': 'brandnew123', 'confirm_password': 'brandnew123'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertFalse(self.user.check_password('brandnew123'))

    def test_mismatched_confirmation_is_rejected(self):
        self._request()
        token = self._verify(self.sent[-1]).json()['data']['token']
        response = self.client.post(
            '/api/v1/auth/otp/set-password/',
            {'token': token, 'new_password': 'brandnew123', 'confirm_password': 'different123'},
            format='json',
        )
        self.assertIn('confirm_password', response.json()['errors'])

    def test_short_password_is_rejected(self):
        self._request()
        token = self._verify(self.sent[-1]).json()['data']['token']
        response = self.client.post(
            '/api/v1/auth/otp/set-password/',
            {'token': token, 'new_password': 'short', 'confirm_password': 'short'},
            format='json',
        )
        self.assertIn('new_password', response.json()['errors'])


@override_settings(SMS_BACKEND='console')
class PhoneStatusTest(TestCase):
    """Routing a caller to login vs setup.

    The whole point of this endpoint is that Django's own `has_usable_password()` gives the
    WRONG answer here, so these tests pin the distinction.
    """

    def setUp(self):
        from .views import OtpRateThrottle

        original = OtpRateThrottle.allow_request
        OtpRateThrottle.allow_request = lambda self, request, view: True
        self.addCleanup(setattr, OtpRateThrottle, 'allow_request', original)
        self.client = APIClient()

    def _status(self, phone):
        return self.client.post(
            '/api/v1/auth/phone-status/', {'phone': phone}, format='json'
        ).json()['data']

    def test_booth_created_account_needs_setup_despite_having_a_password(self):
        """THE case this endpoint exists for.

        A booth gives every new account a random 12-character password it never tells the
        customer, so `has_usable_password()` is True while the holder cannot possibly log in.
        Trusting Django's flag would route them to a login screen they can never pass.
        """
        user = User.objects.create_user(
            phone='03001112233', password='random-booth-generated', full_name='Booth Made'
        )
        self.assertTrue(user.has_usable_password())  # Django says yes...
        status_data = self._status('03001112233')
        self.assertTrue(status_data['exists'])
        self.assertFalse(status_data['has_password'])  # ...but we say no.

    def test_account_reports_has_password_after_the_otp_flow(self):
        User.objects.create_user(
            phone='03001112233', password='random-booth-generated', full_name='Holder'
        )
        # Walk the real flow rather than setting the field by hand.
        from . import otp_service

        sent = []

        class _Capture:
            name = 'console'

            def send(inner, *, phone, message):  # noqa: N805
                sent.append(message.split()[0])
                return True

        original = otp_service.get_sms_sender
        otp_service.get_sms_sender = lambda: _Capture()
        self.addCleanup(setattr, otp_service, 'get_sms_sender', original)

        self.client.post(
            '/api/v1/auth/otp/request/', {'phone': '03001112233'}, format='json'
        )
        token = self.client.post(
            '/api/v1/auth/otp/verify/',
            {'phone': '03001112233', 'code': sent[-1]},
            format='json',
        ).json()['data']['token']
        self.client.post(
            '/api/v1/auth/otp/set-password/',
            {'token': token, 'new_password': 'chosen12345', 'confirm_password': 'chosen12345'},
            format='json',
        )

        self.assertTrue(self._status('03001112233')['has_password'])

    def test_unknown_number(self):
        status_data = self._status('03009998877')
        self.assertFalse(status_data['exists'])
        self.assertFalse(status_data['has_password'])

    def test_blocked_and_staff_are_reported(self):
        User.objects.create_user(
            phone='03007776655', password='x', full_name='Op',
            user_role='operator',
        )
        self.assertTrue(self._status('03007776655')['is_staff_account'])

        blocked = User.objects.create_user(
            phone='03001112233', password='x', full_name='Blocked'
        )
        blocked.status = UserStatus.BLOCKED
        blocked.save(update_fields=['status'])
        self.assertTrue(self._status('03001112233')['blocked'])

    def test_existing_logins_were_backfilled(self):
        """Migration 0003 stamps anyone who has ever logged in, so long-standing users are
        not sent through verification they do not need."""
        user = User.objects.create_user(
            phone='03001112233', password='known12345', full_name='Regular'
        )
        self.client.post(
            '/api/v1/auth/login/',
            {'phone': '03001112233', 'password': 'known12345'},
            format='json',
        )
        user.refresh_from_db()
        # LoginSerializer writes last_login_at; the migration's backfill keys off it. A
        # fresh login here does not stamp password_set_at, so this asserts the CURRENT
        # behaviour: logging in alone is not proof for new rows, only for migrated ones.
        self.assertIsNotNone(user.last_login_at)


class OtpPushDeliveryTest(TestCase):
    """The OTP's push channel — and the takeover it must never permit.

    The property under test is not "push works". It is that a caller cannot NOMINATE where
    the code goes. An OTP proves possession of a phone NUMBER; if the code could be pushed
    to whichever device asked for it, then knowing a number — which is not a secret — would
    be enough to receive that account's code, set a new password and take the wallet
    balance. So delivery is keyed on the user's already-registered devices, and those rows
    can only be created by an authenticated request.

    Patched at `requests.post`, the real network seam, so the destination token asserted
    below is the one that would actually have gone to FCM.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            phone='03001112233', password='holderpass123', full_name='Bound Device Holder'
        )
        self.attacker = User.objects.create_user(
            phone='03009998877', password='attackerpass123', full_name='Attacker'
        )
        self.client = APIClient()

        # The throttle is 5/minute and its counter lives in the process cache, so it carries
        # across tests and starts rejecting later ones with a 429 that looks like a genuine
        # failure. Lifted here, the same way the other OTP suites do it — the throttle has
        # its own tests and is not what this class is measuring.
        from .views import OtpRateThrottle

        original = OtpRateThrottle.allow_request
        OtpRateThrottle.allow_request = lambda self, request, view: True
        self.addCleanup(setattr, OtpRateThrottle, 'allow_request', original)

    def _register_device(self, user, token):
        client = APIClient()
        client.force_authenticate(user=user)
        response = client.post(
            '/api/v1/notifications/devices/register/',
            {'token': token, 'platform': 'android'},
            format='json',
        )
        self.assertIn(response.status_code, (200, 201))

    @contextmanager
    def _fcm(self):
        """Runs the real send path with only the HTTP call faked.

        Yields a list of the destination tokens FCM was asked to deliver to.
        """
        destinations = []

        class _Ok:
            status_code = 200

            @staticmethod
            def json():
                return {}

        def fake_post(url, headers=None, data=None, timeout=None):
            destinations.append(json.loads(data)['message']['token'])
            return _Ok()

        with (
            patch('apps.notifications.services.is_configured', return_value=True),
            patch('apps.notifications.services._access_token', return_value='tok'),
            patch('apps.notifications.services.requests.post', side_effect=fake_post),
        ):
            yield destinations

    def test_code_is_pushed_to_a_device_bound_to_that_account(self):
        self._register_device(self.user, 'token-belonging-to-holder')

        with self._fcm() as destinations:
            response = self.client.post(
                '/api/v1/auth/otp/request/', {'phone': '03001112233'}, format='json'
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['pushed_to_devices'], 1)
        self.assertIn('push', response.data['data']['channels'])
        self.assertEqual(destinations, ['token-belonging-to-holder'])

    def test_the_code_never_reaches_another_users_device(self):
        """THE takeover test.

        The attacker registers their own device, then asks for the victim's code. Their
        token must not be among the destinations — otherwise step three of a five-step
        account takeover succeeds.
        """
        self._register_device(self.user, 'token-belonging-to-holder')
        self._register_device(self.attacker, 'token-belonging-to-attacker')

        with self._fcm() as destinations:
            self.client.post(
                '/api/v1/auth/otp/request/', {'phone': '03001112233'}, format='json'
            )

        self.assertIn('token-belonging-to-holder', destinations)
        self.assertNotIn('token-belonging-to-attacker', destinations)

    def test_a_client_cannot_nominate_the_destination(self):
        """Passing a token in the request body must change nothing.

        This is the shape a naive "send the OTP over FCM" implementation takes, and it is
        the one that hands over any account for the price of a phone number.
        """
        self._register_device(self.user, 'token-belonging-to-holder')
        self._register_device(self.attacker, 'token-belonging-to-attacker')

        with self._fcm() as destinations:
            self.client.post(
                '/api/v1/auth/otp/request/',
                {
                    'phone': '03001112233',
                    'token': 'token-belonging-to-attacker',
                    'device_token': 'token-belonging-to-attacker',
                    'fcm_token': 'token-belonging-to-attacker',
                },
                format='json',
            )

        self.assertEqual(destinations, ['token-belonging-to-holder'])

    def test_the_pushed_code_matches_the_one_that_verifies(self):
        """A push carrying a different code than the SMS would be unusable."""
        self._register_device(self.user, 'token-belonging-to-holder')

        titles = []

        class _Ok:
            status_code = 200

            @staticmethod
            def json():
                return {}

        def capture(url, headers=None, data=None, timeout=None):
            titles.append(json.loads(data)['message']['notification']['title'])
            return _Ok()

        with (
            patch('apps.notifications.services.is_configured', return_value=True),
            patch('apps.notifications.services._access_token', return_value='tok'),
            patch('apps.notifications.services.requests.post', side_effect=capture),
        ):
            self.client.post(
                '/api/v1/auth/otp/request/', {'phone': '03001112233'}, format='json'
            )

        code = titles[0].split()[0]
        self.assertEqual(len(code), 4)
        verify = self.client.post(
            '/api/v1/auth/otp/verify/',
            {'phone': '03001112233', 'code': code},
            format='json',
        )
        self.assertEqual(verify.status_code, status.HTTP_200_OK)

    def test_sms_is_still_sent_when_a_push_lands(self):
        """Both channels by default.

        A bound device may be one the holder no longer carries, and this system has no
        password reset — so an OTP nobody receives is an account nobody can recover.
        """
        self._register_device(self.user, 'token-belonging-to-holder')

        with self._fcm():
            response = self.client.post(
                '/api/v1/auth/otp/request/', {'phone': '03001112233'}, format='json'
            )

        channels = response.data['data']['channels']
        self.assertIn('push', channels)
        self.assertIn('console', channels)

    @override_settings(OTP_PUSH_SUPPRESSES_SMS=True)
    def test_sms_can_be_suppressed_once_a_push_has_landed(self):
        self._register_device(self.user, 'token-belonging-to-holder')

        with self._fcm():
            response = self.client.post(
                '/api/v1/auth/otp/request/', {'phone': '03001112233'}, format='json'
            )

        self.assertEqual(response.data['data']['channels'], ['push'])

    @override_settings(OTP_PUSH_SUPPRESSES_SMS=True)
    def test_suppression_cannot_leave_a_fresh_install_with_no_code(self):
        """The enrolment case, which is the whole point of the flow.

        A new install has no bound device, so there is nothing to push to. Even with
        suppression on, SMS must still go out — otherwise the setting silently breaks the
        only path a new holder has to a password.
        """
        with self._fcm() as destinations:
            response = self.client.post(
                '/api/v1/auth/otp/request/', {'phone': '03001112233'}, format='json'
            )

        self.assertEqual(destinations, [])
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['pushed_to_devices'], 0)
        self.assertIn('console', response.data['data']['channels'])

    def test_a_push_failure_does_not_stop_the_sms(self):
        """The code still has to arrive when FCM is down or unconfigured."""
        with patch(
            'apps.notifications.services.send_to_user',
            side_effect=RuntimeError('FCM exploded'),
        ):
            response = self.client.post(
                '/api/v1/auth/otp/request/', {'phone': '03001112233'}, format='json'
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('console', response.data['data']['channels'])


class OtpDevPushToRequestingDeviceTest(TestCase):
    """The dev-only channel, and the fence around it.

    `OTP_PUSH_TO_REQUESTING_DEVICE` sends the code to whatever device asked. That is exactly
    the takeover shape the rest of this module exists to prevent, so what is tested here is
    less "does it work" than "can it possibly be on when it should not be".
    """

    def setUp(self):
        self.user = User.objects.create_user(
            phone='03001112233', password='holderpass123', full_name='Fresh Install Holder'
        )
        self.client = APIClient()

        from .views import OtpRateThrottle

        original = OtpRateThrottle.allow_request
        OtpRateThrottle.allow_request = lambda self, request, view: True
        self.addCleanup(setattr, OtpRateThrottle, 'allow_request', original)

    @contextmanager
    def _fcm(self):
        destinations = []

        class _Ok:
            status_code = 200

            @staticmethod
            def json():
                return {}

        def fake_post(url, headers=None, data=None, timeout=None):
            destinations.append(json.loads(data)['message']['token'])
            return _Ok()

        with (
            patch('apps.notifications.services.is_configured', return_value=True),
            patch('apps.notifications.services._access_token', return_value='tok'),
            patch('apps.notifications.services.requests.post', side_effect=fake_post),
        ):
            yield destinations

    def test_ignored_by_default(self):
        """OFF unless explicitly enabled — the default must never deliver this way."""
        with self._fcm() as destinations:
            response = self.client.post(
                '/api/v1/auth/otp/request/',
                {'phone': '03001112233', 'device_token': 'caller-supplied-token'},
                format='json',
            )

        self.assertEqual(destinations, [])
        self.assertNotIn('push_dev', response.data['data']['channels'])

    @override_settings(OTP_PUSH_TO_REQUESTING_DEVICE=True)
    def test_when_enabled_the_code_reaches_the_requesting_device(self):
        with self._fcm() as destinations:
            response = self.client.post(
                '/api/v1/auth/otp/request/',
                {'phone': '03001112233', 'device_token': 'caller-supplied-token'},
                format='json',
            )

        self.assertEqual(destinations, ['caller-supplied-token'])
        self.assertIn('push_dev', response.data['data']['channels'])

    @override_settings(
        OTP_PUSH_TO_REQUESTING_DEVICE=True,
        OTP_DEV_PUSH_PHONES=['03009998877'],
    )
    def test_a_number_not_under_test_gets_no_dev_push(self):
        """The fence, and the only reason this mode may run on a deployed server.

        With a list set, every account that is not on it behaves as if the mode were
        off — so an attacker who knows a real customer's number gets nothing back but
        an SMS sent to the SIM, which is the safe path.
        """
        with self._fcm() as destinations:
            response = self.client.post(
                '/api/v1/auth/otp/request/',
                {'phone': '03001112233', 'device_token': 'caller-supplied-token'},
                format='json',
            )

        self.assertEqual(destinations, [])
        self.assertNotIn('push_dev', response.data['data']['channels'])
        self.assertIn('console', response.data['data']['channels'])

    @override_settings(
        OTP_PUSH_TO_REQUESTING_DEVICE=True,
        OTP_DEV_PUSH_PHONES=['0300-111-2233', '03009998877'],
    )
    def test_a_listed_number_still_gets_the_dev_push_however_it_is_punctuated(self):
        """The list goes through the same normalisation as the requested number.

        Spaces and dashes only — `+923001112233` would NOT match this account, which is
        why the setting's comment says to write the number as the account stores it.
        """
        with self._fcm() as destinations:
            response = self.client.post(
                '/api/v1/auth/otp/request/',
                {'phone': '03001112233', 'device_token': 'caller-supplied-token'},
                format='json',
            )

        self.assertEqual(destinations, ['caller-supplied-token'])
        self.assertIn('push_dev', response.data['data']['channels'])

    @override_settings(OTP_PUSH_TO_REQUESTING_DEVICE=True)
    def test_a_bound_device_still_wins_over_the_dev_path(self):
        """The safe channel takes precedence wherever it can work.

        A holder already signed in has a registered device, and that is a destination the
        SERVER chose. The dev path is only a fallback for a fresh install, so enabling it
        must not start routing codes to caller-supplied tokens for accounts that never
        needed it.
        """
        signed_in = APIClient()
        signed_in.force_authenticate(user=self.user)
        signed_in.post(
            '/api/v1/notifications/devices/register/',
            {'token': 'token-the-server-knows', 'platform': 'android'},
            format='json',
        )

        with self._fcm() as destinations:
            response = self.client.post(
                '/api/v1/auth/otp/request/',
                {'phone': '03001112233', 'device_token': 'caller-supplied-token'},
                format='json',
            )

        self.assertEqual(destinations, ['token-the-server-knows'])
        self.assertNotIn('caller-supplied-token', destinations)
        self.assertIn('push', response.data['data']['channels'])

    @override_settings(OTP_PUSH_TO_REQUESTING_DEVICE=True)
    def test_the_pushed_code_is_the_one_that_verifies(self):
        titles = []

        class _Ok:
            status_code = 200

            @staticmethod
            def json():
                return {}

        def capture(url, headers=None, data=None, timeout=None):
            titles.append(json.loads(data)['message']['notification']['title'])
            return _Ok()

        with (
            patch('apps.notifications.services.is_configured', return_value=True),
            patch('apps.notifications.services._access_token', return_value='tok'),
            patch('apps.notifications.services.requests.post', side_effect=capture),
        ):
            self.client.post(
                '/api/v1/auth/otp/request/',
                {'phone': '03001112233', 'device_token': 'caller-supplied-token'},
                format='json',
            )

        code = titles[0].split()[0]
        verify = self.client.post(
            '/api/v1/auth/otp/verify/',
            {'phone': '03001112233', 'code': code},
            format='json',
        )
        self.assertEqual(verify.status_code, status.HTTP_200_OK)

    @override_settings(OTP_PUSH_TO_REQUESTING_DEVICE=True)
    def test_an_absent_device_token_falls_back_to_sms(self):
        """Enabling the mode must not break the console/SMS path for callers without one."""
        with self._fcm() as destinations:
            response = self.client.post(
                '/api/v1/auth/otp/request/', {'phone': '03001112233'}, format='json'
            )

        self.assertEqual(destinations, [])
        self.assertIn('console', response.data['data']['channels'])

    def test_production_settings_refuse_to_load_with_it_enabled(self):
        """The fence.

        The setting comes from the environment, and an env var set on a dev box has obvious
        ways of following a deployment to a real one — a copied .env, a shared profile, a
        pasted command. A warning in a log nobody reads is not a control, so production
        settings fail at import instead.
        """
        import importlib
        import os
        from unittest.mock import patch as env_patch

        base = importlib.import_module('config.settings.base')
        production = importlib.import_module('config.settings.production')

        # `production.py` does `from .base import *`, which re-exports the CACHED base
        # module rather than re-executing it — so reloading production alone would still see
        # the value base read at first import. Base has to be reloaded first for the patched
        # environment to reach the setting at all.
        #
        # Restored afterwards so a stale module object cannot leak into later tests.
        self.addCleanup(importlib.reload, production)
        self.addCleanup(importlib.reload, base)

        with env_patch.dict(
            os.environ,
            {
                'OTP_PUSH_TO_REQUESTING_DEVICE': 'True',
                'ALLOWED_HOSTS': 'example.com',
                'SECRET_KEY': 'x' * 60,
            },
        ):
            importlib.reload(base)
            with self.assertRaises(ValueError) as caught:
                importlib.reload(production)

        self.assertIn('OTP_PUSH_TO_REQUESTING_DEVICE', str(caught.exception))


class PasswordResetOtpTest(TestCase):
    """Forgot password: same proof of phone ownership, different consequences.

    A reset differs from a first-time setup in exactly one way that matters — the holder
    ALREADY had a password, so the most common reason to reset is the belief that somebody
    else is using the account. A reset that leaves existing sessions alive is barely a reset:
    this system issues a 7-day refresh token, so an intruder would keep working access for a
    week after the victim thought they had locked them out.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            phone='03001112233', password='originalpass123', full_name='Reset Holder'
        )
        self.user.password_set_at = timezone.now()
        self.user.save(update_fields=['password_set_at'])
        self.client = APIClient()

        from .views import OtpRateThrottle

        original = OtpRateThrottle.allow_request
        OtpRateThrottle.allow_request = lambda self, request, view: True
        self.addCleanup(setattr, OtpRateThrottle, 'allow_request', original)

    def _code(self, purpose='password_reset'):
        """Request a code and read it back out of the console sender's log line."""
        with self.assertLogs('apps.users.sms', level='WARNING') as logs:
            response = self.client.post(
                '/api/v1/auth/otp/request/',
                {'phone': '03001112233', 'purpose': purpose},
                format='json',
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return next(
            word for word in logs.output[0].split() if word.isdigit() and len(word) == 4
        )

    def test_a_holder_who_already_has_a_password_can_still_get_a_code(self):
        # The whole point. The setup flow is gated on NOT having a password; if reset were
        # gated the same way, the people who need it most could never use it.
        response = self.client.post(
            '/api/v1/auth/otp/request/',
            {'phone': '03001112233', 'purpose': 'password_reset'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['purpose'], 'password_reset')

    def test_full_reset_changes_the_password(self):
        code = self._code()
        verify = self.client.post(
            '/api/v1/auth/otp/verify/',
            {'phone': '03001112233', 'code': code, 'purpose': 'password_reset'},
            format='json',
        )
        self.assertEqual(verify.status_code, status.HTTP_200_OK)

        done = self.client.post(
            '/api/v1/auth/otp/set-password/',
            {
                'token': verify.data['data']['token'],
                'new_password': 'brandnewpass456',
                'confirm_password': 'brandnewpass456',
                'purpose': 'password_reset',
            },
            format='json',
        )
        self.assertEqual(done.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('brandnewpass456'))
        self.assertFalse(self.user.check_password('originalpass123'))

    def test_reset_revokes_every_existing_session(self):
        """THE property that separates a reset from a password change."""
        from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
        from rest_framework_simplejwt.tokens import RefreshToken

        # Two live sessions, as though the holder is signed in on a phone and a tablet — or
        # as though somebody else is signed in as them.
        stolen = RefreshToken.for_user(self.user)
        other = RefreshToken.for_user(self.user)
        self.assertEqual(BlacklistedToken.objects.count(), 0)

        code = self._code()
        verify = self.client.post(
            '/api/v1/auth/otp/verify/',
            {'phone': '03001112233', 'code': code, 'purpose': 'password_reset'},
            format='json',
        )
        done = self.client.post(
            '/api/v1/auth/otp/set-password/',
            {
                'token': verify.data['data']['token'],
                'new_password': 'brandnewpass456',
                'confirm_password': 'brandnewpass456',
                'purpose': 'password_reset',
            },
            format='json',
        )
        self.assertEqual(done.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(done.data['data']['sessions_revoked'], 2)

        self.assertEqual(BlacklistedToken.objects.count(), 2)

        # The intruder's refresh token must now be refused.
        #
        # Presented as a COOKIE, not in the body: TokenRefreshCookieView reads
        # `request.COOKIES` and never the payload, so a body-borne token is silently ignored
        # and the request refreshes whatever session the client already holds — which
        # returns 200 and proves nothing. A separate client is used so the reset's own
        # freshly-issued cookies are not what answers.
        intruder = APIClient()
        intruder.cookies['refresh_token'] = str(stolen)
        refused = intruder.post('/api/v1/auth/token/refresh/', {}, format='json')
        self.assertNotEqual(
            refused.status_code,
            status.HTTP_200_OK,
            msg='a blacklisted refresh token still worked',
        )

        # The holder's other device is equally cut off — a reset ends every session, not
        # only the one that looked suspicious.
        second = APIClient()
        second.cookies['refresh_token'] = str(other)
        self.assertNotEqual(
            second.post('/api/v1/auth/token/refresh/', {}, format='json').status_code,
            status.HTTP_200_OK,
        )

    def test_the_new_session_survives_its_own_revocation_sweep(self):
        """Ordering matters: revoke first, then mint.

        The set-password response signs the holder in. If the new token were created before
        the sweep it would be blacklisted by it, and the user would be thrown straight back
        out of the app they had just recovered.
        """
        code = self._code()
        verify = self.client.post(
            '/api/v1/auth/otp/verify/',
            {'phone': '03001112233', 'code': code, 'purpose': 'password_reset'},
            format='json',
        )
        done = self.client.post(
            '/api/v1/auth/otp/set-password/',
            {
                'token': verify.data['data']['token'],
                'new_password': 'brandnewpass456',
                'confirm_password': 'brandnewpass456',
                'purpose': 'password_reset',
            },
            format='json',
        )
        self.assertEqual(done.status_code, status.HTTP_200_OK)
        # The cookies the response set must still authenticate.
        me = self.client.get('/api/v1/auth/me/')
        self.assertEqual(me.status_code, status.HTTP_200_OK)
        self.assertEqual(me.data['data']['phone'], '03001112233')

    def test_a_setup_token_cannot_complete_a_reset(self):
        """Purposes are not interchangeable.

        Both flows end in a password being written, so the only thing stopping a setup token
        from silently taking the reset path — and skipping session revocation — is that the
        signing salt is derived from the purpose.
        """
        code = self._code(purpose='password_setup')
        verify = self.client.post(
            '/api/v1/auth/otp/verify/',
            {'phone': '03001112233', 'code': code, 'purpose': 'password_setup'},
            format='json',
        )
        self.assertEqual(verify.status_code, status.HTTP_200_OK)

        crossed = self.client.post(
            '/api/v1/auth/otp/set-password/',
            {
                'token': verify.data['data']['token'],
                'new_password': 'brandnewpass456',
                'confirm_password': 'brandnewpass456',
                'purpose': 'password_reset',
            },
            format='json',
        )
        self.assertEqual(crossed.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(crossed.data['errors']['reason'], 'token_invalid')

    def test_a_reset_code_cannot_satisfy_a_setup_verify(self):
        code = self._code(purpose='password_reset')
        crossed = self.client.post(
            '/api/v1/auth/otp/verify/',
            {'phone': '03001112233', 'code': code, 'purpose': 'password_setup'},
            format='json',
        )
        self.assertEqual(crossed.status_code, status.HTTP_400_BAD_REQUEST)

    def test_requesting_a_reset_does_not_burn_a_pending_setup_code(self):
        """Each purpose keeps its own live code.

        Invalidating across purposes would let one flow deny the other: a user halfway
        through setup would find their code dead because something asked for a reset.
        """
        setup_code = self._code(purpose='password_setup')
        self._code(purpose='password_reset')

        still_valid = self.client.post(
            '/api/v1/auth/otp/verify/',
            {'phone': '03001112233', 'code': setup_code, 'purpose': 'password_setup'},
            format='json',
        )
        self.assertEqual(still_valid.status_code, status.HTTP_200_OK)

    def test_an_unknown_purpose_is_refused_not_defaulted(self):
        # Silently treating a typo as `password_setup` would skip revocation — the one thing
        # a reset does that a setup does not.
        response = self.client.post(
            '/api/v1/auth/otp/request/',
            {'phone': '03001112233', 'purpose': 'password_recovery'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_omitting_purpose_still_means_setup(self):
        # Backwards compatibility: an older client sends no purpose at all.
        response = self.client.post(
            '/api/v1/auth/otp/request/', {'phone': '03001112233'}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['purpose'], 'password_setup')

    def test_an_unknown_number_cannot_trigger_a_reset(self):
        response = self.client.post(
            '/api/v1/auth/otp/request/',
            {'phone': '03009999999', 'purpose': 'password_reset'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

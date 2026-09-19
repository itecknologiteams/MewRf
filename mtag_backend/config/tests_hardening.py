"""The configuration invariants in config/settings/hardening.py.

Worth testing because the failure they guard against is silent: the checks used
to live only in `config.settings.production`, nothing loaded that module, and so
nothing enforced them. A test is what notices if they stop being called again.
"""

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config.settings.hardening import MIN_SECRET_KEY_LENGTH, enforce

SAFE = {
    'settings_module': 'config.settings.lan',
    'secret_key': 'k' * 50,
    'debug': False,
    'allowed_hosts': ['192.168.78.200', 'api.maliroperations.com'],
    'otp_push_to_requesting_device': False,
}


def _with(**overrides):
    kwargs = dict(SAFE)
    kwargs.update(overrides)
    return kwargs


class HardeningGuardTests(SimpleTestCase):
    def test_a_correct_deployment_boots(self):
        enforce(**SAFE)  # must not raise

    def test_a_real_booth_config_boots(self):
        enforce(**_with(allowed_hosts=['localhost', '127.0.0.1', '192.168.78.49']))

    def test_debug_is_refused(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'DEBUG is on'):
            enforce(**_with(debug=True))

    def test_placeholder_secret_key_is_refused(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'placeholder'):
            enforce(**_with(secret_key='your-secret-key-here'))

    def test_empty_secret_key_is_refused(self):
        with self.assertRaises(ImproperlyConfigured):
            enforce(**_with(secret_key=''))

    def test_short_secret_key_is_refused(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'characters'):
            enforce(**_with(secret_key='k' * (MIN_SECRET_KEY_LENGTH - 1)))

    def test_secret_key_at_the_minimum_is_accepted(self):
        enforce(**_with(secret_key='k' * MIN_SECRET_KEY_LENGTH))

    def test_wildcard_allowed_hosts_is_refused(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "ALLOWED_HOSTS contains '*'"):
            enforce(**_with(allowed_hosts=['*']))

    def test_wildcard_hidden_among_real_hosts_is_still_refused(self):
        with self.assertRaises(ImproperlyConfigured):
            enforce(**_with(allowed_hosts=['10.0.0.1', 'api.example.com', '*']))

    def test_otp_takeover_mode_is_refused(self):
        with self.assertRaisesMessage(
            ImproperlyConfigured, 'OTP_PUSH_TO_REQUESTING_DEVICE'
        ):
            enforce(**_with(otp_push_to_requesting_device=True))

    def test_open_cors_with_credentials_is_refused(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'CORS_ALLOW_ALL_ORIGINS'):
            enforce(**_with(cors_allow_all_origins=True, cors_allow_credentials=True))

    def test_open_cors_without_credentials_is_allowed(self):
        """Without credentials it exposes no authenticated data, so it is not
        this check's business to refuse it."""
        enforce(**_with(cors_allow_all_origins=True, cors_allow_credentials=False))

    def test_the_message_names_the_settings_module(self):
        """A failed deploy should say which file to open."""
        with self.assertRaisesMessage(ImproperlyConfigured, 'config.settings.production'):
            enforce(**_with(
                settings_module='config.settings.production', debug=True))


class LiveSettingsTests(SimpleTestCase):
    def test_the_running_configuration_satisfies_the_invariants(self):
        """Whatever settings module this suite runs under must itself be sound.

        Catches the case the guards exist but the module under test bypasses
        them — which is exactly how they came to be dead code before.
        """
        from django.conf import settings

        if settings.DEBUG:
            self.skipTest('development settings — the guards do not apply')
        enforce(
            settings_module=settings.SETTINGS_MODULE,
            secret_key=settings.SECRET_KEY,
            debug=settings.DEBUG,
            allowed_hosts=settings.ALLOWED_HOSTS,
            otp_push_to_requesting_device=settings.OTP_PUSH_TO_REQUESTING_DEVICE,
            cors_allow_all_origins=getattr(settings, 'CORS_ALLOW_ALL_ORIGINS', False),
            cors_allow_credentials=getattr(settings, 'CORS_ALLOW_CREDENTIALS', False),
        )

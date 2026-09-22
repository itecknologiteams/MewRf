"""
LAN / internal-network deployment settings.
Use this when the server is on a private LAN without HTTPS.
DJANGO_SETTINGS_MODULE=config.settings.lan
"""
from .base import *

DEBUG = False

# ALLOWED_HOSTS must be set in .env (comma-separated IPs/hostnames)
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')

# CORS origins set from .env
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[])

# ── Security (LAN-safe — no SSL redirect since LAN is HTTP-only) ──────────────
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# SSL is NOT enabled on LAN — do not redirect or set HSTS
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# ── Configuration invariants ─────────────────────────────────────────────────
# This is the module every deployment actually loads, so this is where the
# checks have to be. See config/settings/hardening.py for why each one refuses
# to boot rather than warning.
from .hardening import enforce  # noqa: E402

enforce(
    settings_module='config.settings.lan',
    secret_key=SECRET_KEY,
    debug=DEBUG,
    allowed_hosts=ALLOWED_HOSTS,
    otp_push_to_requesting_device=OTP_PUSH_TO_REQUESTING_DEVICE,  # noqa: F405
    otp_dev_push_phones=OTP_DEV_PUSH_PHONES,  # noqa: F405
    # The one module that may run the dev OTP push, and only fenced to the numbers
    # in OTP_DEV_PUSH_PHONES. This is the deployment that has no SMS gateway and
    # real handsets to test against; production has neither excuse.
    scoped_otp_dev_push_permitted=True,
    cors_allow_all_origins=globals().get('CORS_ALLOW_ALL_ORIGINS', False),
    cors_allow_credentials=globals().get('CORS_ALLOW_CREDENTIALS', False),
)

# Say so on every boot, at the top of the log the deployer is already watching.
#
# `print` rather than `logging`: LOGGING is not configured until django.setup() runs,
# which is after this module finishes importing, so a log record here goes nowhere.
# Once per gunicorn worker, which is noise worth having — the mode is a live account
# takeover for the listed numbers and must not be something a server does quietly.
if OTP_PUSH_TO_REQUESTING_DEVICE:  # noqa: F405
    import sys as _sys

    print(
        '*** OTP_PUSH_TO_REQUESTING_DEVICE IS ON for '
        f'{len(OTP_DEV_PUSH_PHONES)} test number(s): '  # noqa: F405
        f'{", ".join(OTP_DEV_PUSH_PHONES)}. '  # noqa: F405
        'Anyone who can reach this API and knows one of those numbers can set its '
        'password and spend its wallet. Turn it off when testing ends.',
        file=_sys.stderr,
        flush=True,
    )

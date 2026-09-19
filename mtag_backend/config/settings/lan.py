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
    cors_allow_all_origins=globals().get('CORS_ALLOW_ALL_ORIGINS', False),
    cors_allow_credentials=globals().get('CORS_ALLOW_CREDENTIALS', False),
)

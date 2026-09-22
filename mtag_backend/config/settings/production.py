from .base import *

# ALLOWED_HOSTS is required in production — no default fallback
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')

# CORS origins must be explicitly set — no wildcard allowed with credentials
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS')

# ─── Security ─────────────────────────────────────────────────────────────────
DEBUG = False
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# ─── Behind nginx ─────────────────────────────────────────────────────────────
# TLS terminates at nginx, so Django only ever sees a plain HTTP request on the loopback.
# Without this it believes the connection is insecure and SECURE_SSL_REDIRECT above sends a
# 301 to https:// — which nginx forwards back as http:// — an infinite redirect loop that
# looks like the app being down.
#
# Safe only because nginx OVERWRITES X-Forwarded-Proto on every request (see
# deploy/nginx-api.maliroperations.com.conf); a client cannot forge it.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True


# ── Configuration invariants ─────────────────────────────────────────────────
# Shared with config.settings.lan rather than duplicated here — the checks that
# only existed in this module went unenforced for as long as nothing loaded it.
from .hardening import enforce  # noqa: E402

enforce(
    settings_module='config.settings.production',
    secret_key=SECRET_KEY,
    debug=DEBUG,
    allowed_hosts=ALLOWED_HOSTS,
    otp_push_to_requesting_device=OTP_PUSH_TO_REQUESTING_DEVICE,  # noqa: F405
    # `scoped_otp_dev_push_permitted` is deliberately NOT passed: the test-number
    # exemption config.settings.lan has does not exist here, because no number on an
    # internet-facing payment API is a test number.
    otp_dev_push_phones=OTP_DEV_PUSH_PHONES,  # noqa: F405
    cors_allow_all_origins=globals().get('CORS_ALLOW_ALL_ORIGINS', False),
    cors_allow_credentials=CORS_ALLOW_CREDENTIALS,  # noqa: F405
)

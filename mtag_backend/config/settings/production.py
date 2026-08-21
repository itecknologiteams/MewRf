from .base import *

# ─── Safety guards ────────────────────────────────────────────────────────────
if SECRET_KEY == 'your-secret-key-here':
    raise ValueError(
        "SECRET_KEY must be set to a cryptographically secure random value. "
        "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(50))\""
    )

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


# ─── Refuse to start with the dev OTP mode on ─────────────────────────────────
# OTP_PUSH_TO_REQUESTING_DEVICE sends the verification code to whatever device asked for it.
# In development that is how the onboarding flow is exercised on a real phone before an SMS
# gateway exists. In production it is a one-step account takeover: an OTP proves possession
# of a phone NUMBER, and a code delivered to the requester's own handset proves only that
# they installed the app — so knowing a customer's number would be enough to receive their
# code, set a new password and empty their wallet.
#
# A hard failure at import, not a warning. The setting is read from the environment, and an
# environment variable set for a dev box has an obvious way of following a deployment to a
# real one — a copied .env, a shared shell profile, a pasted command. A warning in a log
# nobody tails is not a control; refusing to boot is.
if OTP_PUSH_TO_REQUESTING_DEVICE:  # noqa: F405
    raise ValueError(
        'OTP_PUSH_TO_REQUESTING_DEVICE is enabled under production settings. It delivers '
        'verification codes to whichever device requests them, which lets anyone who knows '
        'a phone number take over that account. Unset it, or use SMS_BACKEND for real '
        'delivery.'
    )

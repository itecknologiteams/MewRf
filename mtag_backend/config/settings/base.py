import sys
import environ
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
env = environ.Env()
environ.Env.read_env(BASE_DIR / '.env')

SECRET_KEY = env('SECRET_KEY')
DEBUG = env.bool('DEBUG', default=False)
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost'])

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
    'drf_spectacular',
]

LOCAL_APPS = [
    'apps.users',
    'apps.vehicles',
    'apps.tolls',
    'apps.accounts',
    'apps.payments',
    'apps.notifications',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # must be second, right after SecurityMiddleware
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ── Database — supports primary + local fallback via psycopg2 multi-host ──────
# Set DB_FALLBACK_HOST in .env to enable automatic failover.
# psycopg2 tries DB_HOST first; if unreachable within connect_timeout seconds,
# it transparently switches to DB_FALLBACK_HOST.
_db_primary  = env('DB_HOST',          default='localhost')
_db_fallback = env('DB_FALLBACK_HOST', default='')
_db_port     = env('DB_PORT',          default='5432')
_master_host = env('MASTER_DB_HOST',   default='192.168.78.200')

# TCP keepalives on every connection. The gate holds a connection open per
# thread and only uses it when a tag arrives, so on a quiet lane the socket can
# sit idle for many minutes. Anything in the path that reaps idle connections —
# a NAT table, a firewall, Postgres' own idle_session_timeout — drops it
# silently, and the process finds out only when the next vehicle's query fails.
# Keepalives make the kernel prove the link is alive every 30s, so the socket is
# either kept open or torn down where Django's reconnect logic can see it.
_db_keepalives = {
    'keepalives': 1,
    'keepalives_idle': 30,      # start probing after 30s of silence
    'keepalives_interval': 10,  # then every 10s
    'keepalives_count': 5,      # give up (and drop the socket) after 5 misses
}

# How long a connection may be reused before it is recycled. This only takes
# effect where something calls close_old_connections() — the request cycle does
# it for the web app, and the long-running gate commands now do it at the top of
# each unit of work. Bounding a connection's life is what stops a lane
# inheriting a socket that died during a quiet spell.
_conn_max_age = env.int('DB_CONN_MAX_AGE', default=60)

if _db_fallback and _db_fallback != _db_primary:
    # Multi-host mode: HOST/PORT must be empty so Django doesn't override OPTIONS
    _db_host_cfg  = ''
    _db_port_cfg  = ''
    _db_options   = {
        'host': f'{_db_primary},{_db_fallback}',
        'port': f'{_db_port},{_db_port}',
        'connect_timeout': 3,   # seconds to wait per host before trying next
        'target_session_attrs': 'any',
        **_db_keepalives,
    }
else:
    _db_host_cfg  = _db_primary
    _db_port_cfg  = _db_port
    _db_options   = {'connect_timeout': 3, **_db_keepalives}

DATABASES = {
    'default': {
        'ENGINE':   'django.db.backends.postgresql',
        'NAME':     env('DB_NAME',     default='mtag_db'),
        'USER':     env('DB_USER',     default='postgres'),
        'PASSWORD': env('DB_PASSWORD', default='postgres'),
        'HOST':     _db_host_cfg,
        'PORT':     _db_port_cfg,
        'OPTIONS':  _db_options,
        'CONN_MAX_AGE': _conn_max_age,
    },
    # Explicit single-host connections for sync agent.
    # These bypass multi-host failover — always target one server.
    'local_pg': {
        'ENGINE':   'django.db.backends.postgresql',
        'NAME':     env('DB_NAME',     default='mtag_db'),
        'USER':     env('DB_USER',     default='postgres'),
        'PASSWORD': env('DB_PASSWORD', default='postgres'),
        'HOST':     'localhost',
        'PORT':     _db_port,
        'OPTIONS':  {'connect_timeout': 3, **_db_keepalives},
        'CONN_MAX_AGE': _conn_max_age,
    },
    'master_pg': {
        'ENGINE':   'django.db.backends.postgresql',
        # Falls back to the local DB_NAME/DB_USER/hardcoded password if unset,
        # so existing deployments where master and local share the same DB
        # name/user keep working unchanged. Set these explicitly whenever a
        # booth's local database name/user differs from master's — which is
        # normal, since they're separate physical Postgres instances.
        'NAME':     env('MASTER_DB_NAME',     default=env('DB_NAME', default='mtag_db')),
        'USER':     env('MASTER_DB_USER',     default=env('DB_USER', default='postgres')),
        # Falls back to the LOCAL DB password, matching how NAME/USER above fall
        # back. The previous hardcoded 'superadmin123456' silently went stale the
        # moment master's password changed, and the only symptom was a booth
        # whose sync could not authenticate — with nothing pointing at settings.
        'PASSWORD': env('MASTER_DB_PASSWORD', default=env('DB_PASSWORD', default='postgres')),
        'HOST':     _master_host,
        'PORT':     _db_port,
        'OPTIONS':  {'connect_timeout': 3, **_db_keepalives},
        'CONN_MAX_AGE': _conn_max_age,
    },
}

AUTH_USER_MODEL = 'users.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Karachi'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'apps.users.authentication.CookieJWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'utils.pagination.StandardPagination',
    'PAGE_SIZE': 20,
    'EXCEPTION_HANDLER': 'utils.exceptions.custom_exception_handler',
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_THROTTLE_RATES': {
        'anon': '200/hour',
        'user': '2000/hour',
        'login': '10/minute',
        # Codes cost money and target someone else's phone. Tighter than login.
        'otp': '5/minute',
    },
}

from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=6),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
]
CORS_ALLOW_CREDENTIALS = True

# ANPR gate auto-start (see apps/tolls/apps.py). This is the only thing the
# setting controls. The old SYNC_AGENT_ENABLED name is still honoured as a
# default so existing .env files keep working; it no longer has anything to do
# with syncing, which has been removed outright.
ANPR_GATE_ENABLED = env.bool(
    'ANPR_GATE_ENABLED',
    default=env.bool('SYNC_AGENT_ENABLED', default=True),
)

# ── Settings kept only so a deployed .env does not break ─────────────────────
# Both are read by nothing. They are retained because every booth's .env still
# carries them and django-environ would not care either way, but deleting the
# names from here would remove the only place that records what they meant.
# Drop them once no deployed .env sets them.
#
# GATE_MODE selected which passes the booth<->master sync service ran. Booths
# are online-only now — they have no database of their own — so that service
# and its apps/tolls/sync/ package have been deleted. The gate takes its own
# entry/exit mode from `mode` in rfid_config.ini, and always did.
GATE_MODE = env('GATE_MODE', default='exit')

# ONLINE_ONLY_MODE dates from when the gate wrote to a local DB and to master in
# the same transaction. There is no longer anything to toggle: master is the
# only database a booth has, which is what makes the system online-only. The
# trade-off is deliberate and worth restating — if master is unreachable, the
# lane stops. There is no local fallback and nothing retries in the background.
ONLINE_ONLY_MODE = env.bool('ONLINE_ONLY_MODE', default=False)

# ── Booth code deployment (master only) ──────────────────────────────────────
# Credentials for SSHing into a booth to push code, used by booth_deploy_worker
# and the admin portal's booth-deployment view. These are the same shared values
# deploy_booths.sh uses; they live in master's .env, never in the database.
#
# Leave BOOTH_SSH_PASSWORD empty to use key-based auth instead — then master
# needs its key in each booth's authorized_keys, and sshpass is not required.
BOOTH_SSH_USER = env('BOOTH_SSH_USER', default='iteck')
BOOTH_SSH_PASSWORD = env('BOOTH_SSH_PASSWORD', default='')
# An update reinstalls dependencies and restarts PM2; on a slow booth that is
# minutes, not seconds.
BOOTH_DEPLOY_TIMEOUT = env.int('BOOTH_DEPLOY_TIMEOUT', default=1800)

JAZZCASH_MERCHANT_ID = env('JAZZCASH_MERCHANT_ID', default='')
JAZZCASH_PASSWORD = env('JAZZCASH_PASSWORD', default='')
JAZZCASH_INTEGRITY_SALT = env('JAZZCASH_INTEGRITY_SALT', default='')
JAZZCASH_RETURN_URL = env('JAZZCASH_RETURN_URL', default='')
# Verify pp_SecureHash on incoming JazzCash inquiry/payment requests.
# Keep False until the exact hashing formula is confirmed with JazzCash, then
# set True (and JAZZCASH_INTEGRITY_SALT) so the endpoints reject unsigned calls.
JAZZCASH_VERIFY_HASH = env.bool('JAZZCASH_VERIFY_HASH', default=False)

# The payment callback credits a wallet. With JAZZCASH_VERIFY_HASH off nothing
# proves a callback came from JazzCash, so anyone who can reach the endpoint can
# mark a pending top-up paid — the callback never contacts JazzCash to check.
# It therefore refuses to credit unless the signature is actually being enforced.
#
# Set this True ONLY for a sandbox with no real money behind it. In production
# confirm the hashing formula with JazzCash, set JAZZCASH_INTEGRITY_SALT, and
# turn JAZZCASH_VERIFY_HASH on instead.
JAZZCASH_ALLOW_UNVERIFIED_CALLBACK = env.bool(
    'JAZZCASH_ALLOW_UNVERIFIED_CALLBACK', default=False)

# Upper bound on a single top-up. There was none, so one request could mint an
# arbitrary balance. Raise it deliberately if a legitimate top-up needs more.
MAX_TOPUP_AMOUNT = env('MAX_TOPUP_AMOUNT', default='500000')

# ── Push notifications (FCM HTTP v1) ─────────────────────────────────────────
#
# Both must be set for push to be attempted; absent, every send is skipped with a debug log
# and `/notifications/status/` reports push_available=False. That is the correct state for
# the LAN deployment, which has no internet at all.
#
# The legacy server-key API was shut down by Google in June 2024, so v1 + a service account
# is the only option. The credentials file is a PATH, never the key itself — a service
# account JSON in settings or .env would end up in the repo.
FCM_PROJECT_ID = env('FCM_PROJECT_ID', default='')
FCM_CREDENTIALS_FILE = env('FCM_CREDENTIALS_FILE', default='')

# ── SMS (phone OTP for first-time password setup) ────────────────────────────
# 'console' logs the code instead of sending it — correct for dev and the LAN
# deployment, and it makes the whole flow testable before any gateway account exists.
# See apps/users/sms.py for the seam.
SMS_BACKEND = env('SMS_BACKEND', default='console')
TWILIO_ACCOUNT_SID = env('TWILIO_ACCOUNT_SID', default='')
TWILIO_AUTH_TOKEN = env('TWILIO_AUTH_TOKEN', default='')
TWILIO_FROM = env('TWILIO_FROM', default='')

# Deliver the OTP by PUSH ONLY when the push demonstrably reached a bound device.
#
# Off by default, and the default is the safe one. Turning it on saves the SMS fee for a
# holder who is already signed in on their handset, but it also means a holder whose only
# bound device is a phone they no longer carry receives nothing — and since there is no
# password reset in this system, an OTP nobody receives is an account nobody can recover.
#
# It does NOT change who can receive a code: push only ever goes to DeviceToken rows owned
# by that user, which are created only by an authenticated request. An OTP can never be
# pushed to a device that merely asked for one — see apps/users/otp_service.py for why that
# distinction is an account takeover rather than a nicety.
OTP_PUSH_SUPPRESSES_SMS = env.bool('OTP_PUSH_SUPPRESSES_SMS', default=False)

# DEVELOPMENT ONLY. Push the OTP to whatever device asked for it.
#
# `config.settings.production` raises at import if this is on, because in production it is a
# one-step account takeover: an OTP proves possession of a phone NUMBER, and a code sent to
# the requester's own handset proves only that they installed the app. Anyone knowing a
# customer's number could receive their code, set a new password and take the wallet.
#
# It exists because there is no SMS gateway yet. The console sender writes the code to the
# server log, which is fine for curl and useless for exercising the real app on a real
# phone — so this makes the whole onboarding flow testable end to end until a gateway is
# contracted, at which point it goes back off and SMS becomes the channel of record.
#
# Only ever consulted when the account has NO already-bound device; a returning holder gets
# the safe `send_to_user` path instead. Every use logs a WARNING.
OTP_PUSH_TO_REQUESTING_DEVICE = env.bool('OTP_PUSH_TO_REQUESTING_DEVICE', default=False)

# ── API documentation (drf-spectacular) ──────────────────────────────────────
#
# Served at /api/docs/ (Swagger UI), /api/redoc/ and /api/schema/.
#
# GATED BY DEFAULT. This is an internet-facing payment API: a public schema hands an
# attacker the full surface — every path, every field, every enum — including the operator
# and admin endpoints a consumer must never reach. Set API_DOCS_PUBLIC=true only on a
# deployment you are happy to have indexed.
API_DOCS_ENABLED = env.bool('API_DOCS_ENABLED', default=True)
API_DOCS_PUBLIC = env.bool('API_DOCS_PUBLIC', default=False)

SPECTACULAR_SETTINGS = {
    'TITLE': 'M-Tag API',
    'DESCRIPTION': (
        'Electronic toll collection for the Malir Expressway (Shahra-e-Bhutto), Karachi.\n\n'
        '**Every response is wrapped in an envelope** that the generated schemas below do '
        'NOT show:\n\n'
        '```json\n'
        '{"success": true,  "message": "Success", "data": <the documented shape>}\n'
        '{"success": false, "message": "...",     "errors": {"field": ["..."]}}\n'
        '```\n\n'
        'Paginated endpoints add a sibling `meta` with `count`, `next`, `previous`, '
        '`total_pages`, `current_page`.\n\n'
        '**Authentication is cookie-based.** `POST /auth/login/` returns the user in `data` '
        'and sets `access_token` / `refresh_token` as httpOnly cookies — the JWTs are NOT in '
        'the body. Swagger UI sends cookies automatically once you have logged in, so the '
        '"Authorize" button is not needed.\n\n'
        'Access tokens last 6 hours, refresh 7 days, and refresh tokens ROTATE — two '
        'concurrent refreshes will blacklist each other.'
    ),
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    # Endpoints are grouped by the first path segment after /api/v1/.
    'TAGS': [
        {'name': 'auth', 'description': 'Login, session, and phone-OTP password setup.'},
        {'name': 'accounts', 'description': 'Balances and transactions. Consumer-scoped.'},
        {'name': 'vehicles', 'description': 'Vehicles and tags.'},
        {'name': 'tolls', 'description': 'Plazas, the fare matrix, and trip history.'},
        {'name': 'payments', 'description': 'Top-ups. JazzCash webhooks are gateway-to-server.'},
        {'name': 'notifications', 'description': 'FCM device registration.'},
    ],
    'SORT_OPERATIONS': True,
}

MINIMUM_ACCOUNT_BALANCE = 50

# Allow ANONYMOUS callers to POST /api/v1/auth/register/.
#
# Off by default: there is no phone verification on that endpoint, so with it on
# anyone can create `user` rows against arbitrary phone numbers, including
# numbers belonging to real people who have not signed up. M-Tag accounts are
# created at a booth, by an authenticated operator — that path is unaffected by
# this setting (see apps/users/views.py RegisterView). Turn this on only once
# phone-OTP verification exists.
USER_SELF_REGISTRATION_ENABLED = env.bool('USER_SELF_REGISTRATION_ENABLED', default=False)

# ── Topup receipt printing (POS / ESC-POS via CUPS `lp`) ──────────────────────
# After a successful cash topup the backend prints a TOPUP receipt on the same
# POS80 thermal printer the toll system uses (`lp -d POS80 -o raw`). Best-effort:
# a print failure never fails the topup. Disabled by default so dev/Windows
# machines (no printer) don't error; the gate PC (Linux/CUPS) sets it True.
TOPUP_RECEIPT_PRINT_ENABLED = env.bool('TOPUP_RECEIPT_PRINT_ENABLED', default=False)
POS_PRINTER_NAME = env('POS_PRINTER_NAME', default='POS80')
RECEIPT_LOGO_PATH = env('RECEIPT_LOGO_PATH', default=str(BASE_DIR / 'apps' / 'accounts' / 'receipt_logo.png'))

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {'format': '[{asctime}] {levelname} {name} {message}', 'style': '{'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'verbose'},
    },
    'root': {'handlers': ['console'], 'level': 'INFO'},
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'apps': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': False},
    },
}

# ── Tag issuance ─────────────────────────────────────────────────────────────
# A tag is valid for two years from the day it is issued. Kept here (not as a
# literal in the topup view) so the term can be changed for a new batch without
# touching code, and so the app and the receipt quote the same number.
TAG_VALIDITY_MONTHS = env.int('TAG_VALIDITY_MONTHS', default=24)

# One-off service charge for issuing a tag, taken out of the cash the consumer
# hands over at registration (wallet is credited amount - charge). Only charged
# on registration — a repeat topup on an already-issued tag pays nothing. The
# operator can override the figure per registration; this is the default the
# booth app prefills.
TOPUP_SERVICE_CHARGE = env('TOPUP_SERVICE_CHARGE', default='350.00')

# ── Baseline browser hardening ───────────────────────────────────────────────
# Defaults that hold everywhere, including the HTTP-only LAN deployment. The
# TLS-dependent half (HSTS, SSL redirect, Secure cookies) stays in
# config.settings.production, because switching it on without a certificate in
# front produces a redirect loop that presents as the site being down.

# Auth is a cookie-borne JWT (apps/users/authentication.py) and DRF only enforces
# CSRF for SessionAuthentication, so SameSite is what actually stops cross-site
# forgery here: 'Lax' withholds the cookie on any cross-site POST/PUT/DELETE.
# The login view sets the same attributes on access_token/refresh_token — change
# these two together with apps/users/views.py or the protection is uneven.
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
# Nothing in the frontend reads this cookie from JavaScript (it authenticates
# with the JWT cookie instead), so it can be closed to script — which stops an
# XSS from reading the token and self-submitting a valid form post.
CSRF_COOKIE_HTTPONLY = True

# Hosts allowed to make cross-origin state-changing requests. Empty by default:
# same-origin deployments need nothing here, and a wrong entry is a CSRF bypass.
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[])

# Stop the browser guessing a response is HTML when we said it was JSON — the
# usual route from "uploaded file is echoed back" to stored XSS.
SECURE_CONTENT_TYPE_NOSNIFF = True
# No page here is ever meant to be framed; denying it removes clickjacking.
X_FRAME_OPTIONS = 'DENY'
# Do not leak our paths (which embed IDs) in the Referer of outbound links.
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
# Sever the window handle a page we open keeps to us, and vice versa.
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'

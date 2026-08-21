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

if _db_fallback and _db_fallback != _db_primary:
    # Multi-host mode: HOST/PORT must be empty so Django doesn't override OPTIONS
    _db_host_cfg  = ''
    _db_port_cfg  = ''
    _db_options   = {
        'host': f'{_db_primary},{_db_fallback}',
        'port': f'{_db_port},{_db_port}',
        'connect_timeout': 3,   # seconds to wait per host before trying next
        'target_session_attrs': 'any',
    }
else:
    _db_host_cfg  = _db_primary
    _db_port_cfg  = _db_port
    _db_options   = {'connect_timeout': 3}

DATABASES = {
    'default': {
        'ENGINE':   'django.db.backends.postgresql',
        'NAME':     env('DB_NAME',     default='mtag_db'),
        'USER':     env('DB_USER',     default='postgres'),
        'PASSWORD': env('DB_PASSWORD', default='postgres'),
        'HOST':     _db_host_cfg,
        'PORT':     _db_port_cfg,
        'OPTIONS':  _db_options,
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
        'OPTIONS':  {'connect_timeout': 3},
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
        'OPTIONS':  {'connect_timeout': 3},
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

# ANPR gate auto-start (see apps/tolls/apps.py).
#
# Renamed from SYNC_AGENT_ENABLED, which no longer described what it does: the
# master sync agent is its own process now (`manage.py sync_service` / PM2 app
# `mtag-sync`) and is NOT gated by any setting — it runs because PM2 runs it.
# Leaving the old name would invite someone to set it expecting sync to stop.
# The old name is still honoured so existing .env files keep working.
ANPR_GATE_ENABLED = env.bool(
    'ANPR_GATE_ENABLED',
    default=env.bool('SYNC_AGENT_ENABLED', default=True),
)
# Deprecated alias — read nowhere; kept so old code/config referencing it does
# not silently get a different value than ANPR_GATE_ENABLED.
SYNC_AGENT_ENABLED = ANPR_GATE_ENABLED

# Booth mode — 'entry' or 'exit'. Selects which sync passes the sync service
# runs (see apps/tolls/sync/agent.py):
#   entry  push + pull(reference, closed trips)
#   exit   push + pull(reference, closed trips, OPEN trips)
# An unset or misspelled value degrades to 'exit', the superset: an exit booth
# denied open trips turns paying vehicles away, whereas an entry booth pulling a
# few extra rows costs nothing.
GATE_MODE = env('GATE_MODE', default='exit')

# NO LONGER USED — kept only so an existing .env carrying ONLINE_ONLY_MODE does
# not break, and to document the change.
#
# The gate used to write to the local DB and master synchronously, rejecting the
# transaction outright if master was unreachable — which meant a master outage
# closed every lane. The gate now writes only to its local database, and the
# separate sync service (apps/tolls/sync/, PM2 app mtag-sync) replicates to
# master. Nothing reads this setting; delete it once no deployed .env sets it.
ONLINE_ONLY_MODE = env.bool('ONLINE_ONLY_MODE', default=False)

JAZZCASH_MERCHANT_ID = env('JAZZCASH_MERCHANT_ID', default='')
JAZZCASH_PASSWORD = env('JAZZCASH_PASSWORD', default='')
JAZZCASH_INTEGRITY_SALT = env('JAZZCASH_INTEGRITY_SALT', default='')
JAZZCASH_RETURN_URL = env('JAZZCASH_RETURN_URL', default='')
# Verify pp_SecureHash on incoming JazzCash inquiry/payment requests.
# Keep False until the exact hashing formula is confirmed with JazzCash, then
# set True (and JAZZCASH_INTEGRITY_SALT) so the endpoints reject unsigned calls.
JAZZCASH_VERIFY_HASH = env.bool('JAZZCASH_VERIFY_HASH', default=False)

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

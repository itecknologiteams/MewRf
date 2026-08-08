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
]

LOCAL_APPS = [
    'apps.users',
    'apps.vehicles',
    'apps.tolls',
    'apps.accounts',
    'apps.payments',
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
        'PASSWORD': env('MASTER_DB_PASSWORD', default='superadmin123456'),
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
    'DEFAULT_THROTTLE_RATES': {
        'anon': '200/hour',
        'user': '2000/hour',
        'login': '10/minute',
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

MINIMUM_ACCOUNT_BALANCE = 50

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

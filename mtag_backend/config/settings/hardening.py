"""Configuration invariants that must hold on any non-development deployment.

These used to live in `config.settings.production`. Nothing loads that module —
every deploy path (PM2, both bootstrap scripts, deploy_master.sh) sets
`config.settings.lan` — so every guard in it was dead code, including the one
stopping the OTP account-takeover mode from running in production.

Enforcing them here instead, called from both `lan` and `production`, means the
choice of settings module can no longer decide whether the safety checks apply.
Only `local` is exempt, and it is exempt by not calling this.

Why raise rather than log: these are all cases where the server is running but
not safe to serve. A warning in a log nobody tails is not a control. Refusing to
boot is loud, immediate, and happens on the deployer's terminal.

The checks take their values as arguments rather than reading a settings module,
so they can be exercised directly without standing up Django.
"""

from django.core.exceptions import ImproperlyConfigured

PLACEHOLDER_SECRET_KEYS = frozenset({
    '',
    'your-secret-key-here',
    'changeme',
    'secret',
    'django-insecure-changeme',
})

# Django's own generator emits 50 chars. Anything materially shorter is either a
# hand-typed value or a truncated copy-paste, and it is the single key behind
# every session cookie, JWT signature and password reset token in the system.
MIN_SECRET_KEY_LENGTH = 32


def enforce(
    *,
    settings_module,
    secret_key,
    debug,
    allowed_hosts,
    otp_push_to_requesting_device,
    cors_allow_all_origins=False,
    cors_allow_credentials=False,
):
    """Raise ImproperlyConfigured on any unsafe configuration. Returns nothing.

    `settings_module` appears in every message purely so the operator reading a
    failed deploy knows which file to look in.
    """
    where = f"({settings_module})"

    if debug:
        raise ImproperlyConfigured(
            f"DEBUG is on {where}. Django's debug pages disclose the settings "
            f"module, installed apps, the SQL of the failing query and local "
            f"variables — on a payment API that is a full internal disclosure "
            f"to anyone who can trigger a 500. Set DEBUG=false in .env."
        )

    if secret_key in PLACEHOLDER_SECRET_KEYS:
        raise ImproperlyConfigured(
            f"SECRET_KEY is still the placeholder shipped in .env.example {where}. "
            f"It signs every JWT and session cookie, so a known value lets anyone "
            f"mint a token for any user. Generate one with:\n"
            f"  python -c \"import secrets; print(secrets.token_urlsafe(50))\""
        )

    if len(secret_key) < MIN_SECRET_KEY_LENGTH:
        raise ImproperlyConfigured(
            f"SECRET_KEY is {len(secret_key)} characters {where}; at least "
            f"{MIN_SECRET_KEY_LENGTH} are required. A short key is brute-forceable, "
            f"and forging it forges authentication for every account."
        )

    if '*' in allowed_hosts:
        raise ImproperlyConfigured(
            f"ALLOWED_HOSTS contains '*' {where}. With DEBUG off this accepts any "
            f"Host header, which lets an attacker poison absolute URLs the server "
            f"generates (password-reset and OTP links) so they point at a host they "
            f"control. List this node's real hostnames and IPs instead."
        )

    if otp_push_to_requesting_device:
        raise ImproperlyConfigured(
            f"OTP_PUSH_TO_REQUESTING_DEVICE is enabled {where}. It delivers the "
            f"verification code to whichever device asked for it, so knowing a "
            f"customer's phone number is enough to receive their code, set a new "
            f"password and empty their wallet. Development only — unset it, and set "
            f"SMS_BACKEND for real delivery."
        )

    if cors_allow_all_origins and cors_allow_credentials:
        raise ImproperlyConfigured(
            f"CORS_ALLOW_ALL_ORIGINS is on together with CORS_ALLOW_CREDENTIALS "
            f"{where}. That invites any website to make authenticated requests with "
            f"the visitor's own auth cookie. List the operator UI's origins in "
            f"CORS_ALLOWED_ORIGINS instead."
        )

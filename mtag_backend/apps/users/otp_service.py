"""Issue and verify phone OTPs for first-time password setup.

## Why an OTP cannot be delivered by push ALONE

Push is offered here as an additional channel, never as a replacement for SMS, and the
reason is a complete account takeover rather than a matter of taste.

An OTP proves the requester holds the PHONE NUMBER. SMS establishes that because delivery
is bound to possession of the SIM. FCM delivery is bound to possession of an app install,
which the requester obviously has — so if the code were pushed to whichever device asked
for it, then:

    1. an attacker installs the app and obtains an FCM token,
    2. requests a code for a victim's number (only the number is needed),
    3. receives the code on their OWN device,
    4. verifies, takes the set-password token, and sets a new password,
    5. and now owns the victim's wallet balance.

Knowing someone's mobile number is not a secret, so that is a one-step takeover of any
account on the system.

What IS safe is pushing to devices ALREADY BOUND to the account by a previous authenticated
session — `send_to_user` only ever fans out to `DeviceToken` rows owned by that user, and
those rows can only be created by an authenticated request. So a returning holder who is
still signed in on their phone gets the code instantly and free; a fresh install, which is
the enrolment case, has no bound device and must use SMS. `request_code` therefore reports
which channels actually carried the code rather than claiming success generically.
"""

import logging
import secrets

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core import signing
from django.utils import timezone

from .models import OtpPurpose, PhoneOtp, User
from .sms import get_sms_sender

logger = logging.getLogger(__name__)

#: Four digits, matching the app's OTP screen.
#:
#: 10^4 is only 10,000 combinations, which would be trivially brute-forceable on its own —
#: what makes it acceptable is PhoneOtp.MAX_ATTEMPTS (5 guesses, then the code is burned,
#: not just the guess) plus the 5-minute expiry and the 5/minute request throttle. Raising
#: this to 6 would strengthen it further; lowering MAX_ATTEMPTS' importance would not.
CODE_LENGTH = 4

#: Namespace for the short-lived token handed out after a successful verify. Signed rather
#: than stored: it carries its own expiry and cannot be replayed past it, and there is no
#: extra row to clean up.
#:
#: The PURPOSE is folded into the salt, so a token minted by the setup flow cannot be
#: presented to the reset flow or the other way round. Both end in a password being written,
#: so the practical difference is session revocation — but a token that is valid across
#: purposes is exactly the kind of thing that becomes a hole once a third purpose is added.
_SALT = 'mtag.otp'


def _salt_for(purpose: str) -> str:
    return f'{_SALT}.{purpose}'

#: How long the caller has to choose a password after verifying. Short, because holding a
#: valid set-password token is equivalent to holding the account.
TOKEN_MAX_AGE = 10 * 60


def normalize_phone(raw: str) -> str:
    """Strip spaces and dashes. Stored numbers are bare digits (e.g. 03001234567)."""
    return ''.join(ch for ch in (raw or '') if ch.isdigit() or ch == '+')


def _push_code(user, code: str, purpose: str) -> int:
    """Push the code to devices ALREADY bound to this account. Returns how many got it.

    Safe precisely because it takes a `user`, not a client-supplied token: `send_to_user`
    reads `DeviceToken` rows for that user, and a row can only be created by an
    authenticated `POST /notifications/devices/register/`. There is no way for a caller to
    nominate the destination — see the module docstring for what that would cost.

    The code appears in the notification body, which puts it on the lock screen. That is the
    same exposure SMS already has, and the alternative — a data-only message the user cannot
    read — would deliver nothing.

    Never raises: a push failure must not stop the SMS that follows it.
    """
    try:
        from apps.notifications.services import send_to_user

        return send_to_user(
            user.id,
            title=f'{code} is your M-Tag code',
            body='Expires in 5 minutes. Never share this code with anyone.',
            data={'type': 'otp', 'purpose': purpose},
        )
    except Exception:  # noqa: BLE001
        logger.exception('OTP push failed for user %s', getattr(user, 'id', None))
        return 0


def _push_code_to_requesting_device(
    device_token: str, code: str, purpose: str
) -> bool:
    """DEV ONLY. Push the code to whatever device asked for it.

    Off unless `OTP_PUSH_TO_REQUESTING_DEVICE` is set, and `config.settings.production`
    refuses to start with it on — because in production this IS the account-takeover path
    described in the module docstring. Nothing about the request establishes that the
    caller's handset belongs to the number they typed.

    It exists because there is no SMS gateway yet: the console sender writes the code to the
    server log, which is fine for a curl-driven test and useless for exercising the real app
    on a real phone. This lets the whole onboarding flow — code arrives, auto-verifies,
    password is set — be tested end to end before a gateway contract exists, and it is
    deleted or left off the moment one does.

    Every use logs a WARNING naming the mode, so a deployment running this way cannot do so
    quietly.
    """
    if not device_token:
        return False

    try:
        from apps.notifications.services import send_to_token

        sent = send_to_token(
            device_token,
            title=f'{code} is your M-Tag code',
            body='Expires in 5 minutes. Never share this code with anyone.',
            data={
                'type': 'otp',
                'purpose': purpose,
                # The code itself, so the app can fill it in without the user retyping it.
                #
                # In `data` rather than parsed out of the title: the title is display copy
                # and will be localised, so a client scraping digits from it breaks the day
                # the wording changes. It carries no extra exposure — the same code is
                # already in the notification the lock screen renders.
                #
                # DEV PATH ONLY. The production path (`_push_code`) deliberately does not
                # send this: there the code goes to a device the SERVER chose, the user
                # reads it, and an auto-fill would remove the one human step that makes a
                # pushed code meaningfully different from a typed one.
                'code': code,
            },
        )
    except Exception:  # noqa: BLE001
        logger.exception('Dev OTP push failed')
        return False

    if sent:
        logger.warning(
            'OTP_PUSH_TO_REQUESTING_DEVICE is ON — code delivered to a '
            'caller-supplied device token. This is a DEVELOPMENT mode and must not be '
            'enabled where real accounts exist.'
        )
    return sent


def request_code(
    phone: str,
    device_token: str = '',
    purpose: str = OtpPurpose.PASSWORD_SETUP,
) -> dict:
    """Issue a code for an EXISTING account.

    Returns `{'sent': bool, 'delivery': str, 'reason': str|None}`.

    An unknown number is reported as such rather than silently accepted. That is user
    enumeration, and it is the right trade here: M-Tag accounts are created at a booth from
    a number the operator already holds, so "does this number have an account" is not a
    secret worth protecting — while silently pretending to send would leave a customer
    waiting for an SMS that is never coming, with no way to discover they need to visit a
    plaza.
    """
    phone = normalize_phone(phone)
    user = User.objects.filter(phone=phone).first()
    if user is None:
        return {'sent': False, 'delivery': 'none', 'reason': 'no_account'}
    if user.status == 'blocked':
        return {'sent': False, 'delivery': 'none', 'reason': 'blocked'}

    # Any earlier code for this phone dies now, so an intercepted one cannot be replayed
    # after the user asks for a fresh code.
    # Scoped to THIS purpose. A pending setup code and a pending reset code are different
    # things, and burning one when the other is requested would be a denial of service on a
    # flow the user is halfway through.
    PhoneOtp.objects.filter(
        phone=phone, purpose=purpose, consumed_at__isnull=True
    ).update(consumed_at=timezone.now())

    code = f'{secrets.randbelow(10 ** CODE_LENGTH):0{CODE_LENGTH}d}'
    PhoneOtp.objects.create(
        phone=phone,
        code_hash=make_password(code),
        purpose=purpose,
        expires_at=timezone.now() + PhoneOtp.LIFETIME,
    )

    channels = []

    # Push first: it is instant, free, and reaches a holder who is already signed in on this
    # handset. It reaches NOBODY on a fresh install, which is why it cannot be the only
    # channel.
    pushed = _push_code(user, code, purpose)
    if pushed:
        channels.append('push')

    # DEV ONLY, and only when the bound-device push above found nothing — a fresh install,
    # which is the case the console sender cannot help with on a real phone.
    if (
        not pushed
        and getattr(settings, 'OTP_PUSH_TO_REQUESTING_DEVICE', False)
        and _push_code_to_requesting_device(device_token, code, purpose)
    ):
        channels.append('push_dev')

    # SMS regardless of whether the push landed, unless this deployment has chosen to lean
    # on push when it demonstrably worked. Default is to send both: the bound device might
    # be one the holder no longer carries, and an OTP nobody receives is an account nobody
    # can recover.
    suppress_sms = bool(
        getattr(settings, 'OTP_PUSH_SUPPRESSES_SMS', False)
    ) and pushed
    if suppress_sms:
        logger.info('OTP for %s delivered by push only (%d device(s))', phone, pushed)
    else:
        sender = get_sms_sender()
        if sender.send(
            phone=phone,
            message=f'{code} is your M-Tag verification code. It expires in 5 minutes.',
        ):
            channels.append(sender.name)

    return {
        'sent': bool(channels),
        # Kept as the FIRST channel rather than a list, because the app switches its copy on
        # it ('check your SMS' vs the console-sender notice) and an existing client reads a
        # string here.
        'delivery': channels[0] if channels else 'none',
        'channels': channels,
        'pushed_to': pushed,
        'reason': None if channels else 'send_failed',
    }


def verify_code(
    phone: str,
    code: str,
    purpose: str = OtpPurpose.PASSWORD_SETUP,
) -> dict:
    """Check a code. On success returns a short-lived signed token."""
    phone = normalize_phone(phone)
    otp = (
        PhoneOtp.objects.filter(phone=phone, purpose=purpose)
        .order_by('-created_at')
        .first()
    )
    if otp is None or otp.consumed_at is not None:
        return {'ok': False, 'reason': 'not_found'}
    if otp.is_expired:
        return {'ok': False, 'reason': 'expired'}
    if otp.attempts >= PhoneOtp.MAX_ATTEMPTS:
        return {'ok': False, 'reason': 'too_many_attempts'}

    # Counted BEFORE the comparison, so a crash or a race cannot hand back a free guess.
    otp.attempts += 1
    otp.save(update_fields=['attempts'])

    if not check_password(code or '', otp.code_hash):
        remaining = max(PhoneOtp.MAX_ATTEMPTS - otp.attempts, 0)
        return {'ok': False, 'reason': 'invalid', 'attempts_left': remaining}

    otp.consumed_at = timezone.now()
    otp.save(update_fields=['consumed_at'])
    return {
        'ok': True,
        'token': signing.dumps(
            {'phone': phone, 'purpose': purpose}, salt=_salt_for(purpose)
        ),
    }


def set_password_with_token(
    token: str,
    new_password: str,
    purpose: str = OtpPurpose.PASSWORD_SETUP,
) -> dict:
    """Consume a verify token and set the account's password.

    [purpose] must match the flow the token came from — the salt is derived from it, so a
    setup token presented here as a reset simply fails the signature check rather than
    quietly taking the other path.
    """
    try:
        payload = signing.loads(
            token or '', salt=_salt_for(purpose), max_age=TOKEN_MAX_AGE
        )
    except signing.SignatureExpired:
        return {'ok': False, 'reason': 'token_expired'}
    except signing.BadSignature:
        # Also what a token from the OTHER purpose lands on, which is the intended
        # behaviour: purposes are not interchangeable.
        return {'ok': False, 'reason': 'token_invalid'}

    user = User.objects.filter(phone=payload.get('phone', '')).first()
    if user is None:
        return {'ok': False, 'reason': 'no_account'}

    user.set_password(new_password)
    # Marks this account as one whose holder has chosen a password, so a later visit is
    # routed to login rather than back through verification.
    user.password_set_at = timezone.now()
    user.save(update_fields=['password', 'password_set_at'])

    revoked = 0
    if purpose == OtpPurpose.PASSWORD_RESET:
        revoked = _revoke_sessions(user)

    logger.info(
        'Password %s via OTP for %s (%d session(s) revoked)',
        'reset' if purpose == OtpPurpose.PASSWORD_RESET else 'set',
        user.phone,
        revoked,
    )
    return {'ok': True, 'user': user, 'sessions_revoked': revoked}


def _revoke_sessions(user) -> int:
    """Blacklist every outstanding refresh token for [user]. Returns how many.

    A password reset that leaves existing sessions alive is barely a reset. The common
    reason someone resets is that they believe somebody else is in their account — and this
    system issues a 7-day refresh token, so without this the intruder keeps working access
    for a week after the victim has "locked them out".

    Only refresh tokens can be revoked; the 6-hour access token already issued stays valid
    until it expires, because it is a stateless JWT the server does not consult a store for.
    That is a bounded window rather than an open one, and closing it would mean checking a
    blacklist on every authenticated request.

    Never raises: the password has already been changed by the time this runs, so failing
    here must not report failure for an operation that succeeded.
    """
    try:
        from rest_framework_simplejwt.token_blacklist.models import (
            BlacklistedToken,
            OutstandingToken,
        )

        count = 0
        for outstanding in OutstandingToken.objects.filter(user=user):
            _, created = BlacklistedToken.objects.get_or_create(token=outstanding)
            if created:
                count += 1
        return count
    except Exception:  # noqa: BLE001
        logger.exception('Could not revoke sessions for %s', getattr(user, 'phone', '?'))
        return 0

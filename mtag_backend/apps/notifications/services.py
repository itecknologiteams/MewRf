"""FCM HTTP v1 delivery.

## Why v1 and not the server key

The legacy `fcm.googleapis.com/fcm/send` endpoint — the one every older tutorial uses, with a
static server key — was **shut down by Google in June 2024**. It returns 404 now. v1 is the
only working API, and it authenticates with a short-lived OAuth2 token minted from a service
account, which is why `google-auth` is a dependency.

## Failure policy

**A notification must never break a payment.** Everything here returns rather than raises,
and the caller (signals.py) is additionally wrapped. The worst outcome of a broken FCM
config is that nobody gets told about a top-up that did land — never a top-up that fails
because the notification did.
"""

import json
import logging
import threading

import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

_FCM_SCOPE = 'https://www.googleapis.com/auth/firebase.messaging'
_TIMEOUT = 10

# Credentials are minted once and refreshed in place; building them per send would add a
# token round-trip to every toll deduction.
_credentials = None
_credentials_lock = threading.Lock()


def is_configured() -> bool:
    """Whether push can actually be delivered.

    Read by the views so `/notifications/register/` can tell the app the truth instead of
    accepting tokens into a void.
    """
    return bool(
        getattr(settings, 'FCM_PROJECT_ID', '')
        and getattr(settings, 'FCM_CREDENTIALS_FILE', '')
    )


def _access_token() -> str | None:
    global _credentials
    try:
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account
    except ImportError:
        logger.warning('google-auth is not installed; push disabled')
        return None

    with _credentials_lock:
        if _credentials is None:
            try:
                _credentials = service_account.Credentials.from_service_account_file(
                    settings.FCM_CREDENTIALS_FILE, scopes=[_FCM_SCOPE]
                )
            except (OSError, ValueError, KeyError) as exc:
                logger.error('FCM credentials unusable: %s', exc)
                return None
        try:
            if not _credentials.valid:
                _credentials.refresh(Request())
        except Exception as exc:  # noqa: BLE001 - never propagate into a payment path
            logger.error('FCM token refresh failed: %s', exc)
            return None
        return _credentials.token


def send_to_token(token: str, *, title: str, body: str, data: dict | None = None) -> bool:
    """Deliver to ONE raw token, with no user attached. Returns whether FCM accepted it.

    ## Read this before calling it

    Every other send in this module resolves its destination from a `user_id`, so the
    recipient is whoever the database says owns that device. This one takes the destination
    from the CALLER, which makes the caller responsible for having established that the
    token belongs to the person the message is about.

    That distinction is the entire security boundary of OTP delivery. A code pushed to a
    caller-nominated token proves only that the caller holds an app install — which an
    attacker does — so using this to send a verification code to an unauthenticated
    requester hands over any account for the price of a phone number. See
    `apps/users/otp_service.py` for the full argument.

    Its one legitimate use today is `OTP_PUSH_TO_REQUESTING_DEVICE`, a dev-only switch that
    is off by default and refused outright by production settings.

    Never raises.
    """
    if not is_configured() or not token:
        return False

    access_token = _access_token()
    if not access_token:
        return False

    payload = {
        'message': {
            'token': token,
            'notification': {'title': title, 'body': body},
            'data': {k: str(v) for k, v in (data or {}).items()},
            'android': {
                'priority': 'high',
                'notification': {'channel_id': 'mtag_transactions'},
            },
            'apns': {
                'headers': {'apns-priority': '10'},
                'payload': {'aps': {'sound': 'default'}},
            },
        }
    }

    url = (
        f'https://fcm.googleapis.com/v1/projects/'
        f'{settings.FCM_PROJECT_ID}/messages:send'
    )
    try:
        response = requests.post(
            url,
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json; UTF-8',
            },
            data=json.dumps(payload),
            timeout=_TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.warning('FCM direct send failed (network): %s', exc)
        return False

    if response.status_code == 200:
        return True

    # There is no DeviceToken row to deactivate on failure, because nothing has established
    # whose device this is — which is exactly why this path is dev-only.
    logger.warning(
        'FCM direct send rejected: %s %s',
        response.status_code,
        _error_reason(response),
    )
    return False


def send_to_user(user_id: int, *, title: str, body: str, data: dict | None = None) -> int:
    """Fan out to every active device for one user. Returns the number delivered.

    Never raises.
    """
    if not is_configured():
        logger.debug('Push skipped (FCM not configured): %s', title)
        return 0

    from .models import DeviceToken

    tokens = list(
        DeviceToken.objects.filter(user_id=user_id, is_active=True).values_list(
            'id', 'token'
        )
    )
    if not tokens:
        return 0

    access_token = _access_token()
    if not access_token:
        return 0

    url = (
        f'https://fcm.googleapis.com/v1/projects/'
        f'{settings.FCM_PROJECT_ID}/messages:send'
    )
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json; UTF-8',
    }

    delivered = 0
    for token_id, token in tokens:
        # FCM v1 requires every data value to be a STRING. An int here is rejected with a
        # 400 that reads like a malformed message rather than a type error.
        payload = {
            'message': {
                'token': token,
                'notification': {'title': title, 'body': body},
                'data': {k: str(v) for k, v in (data or {}).items()},
                'android': {
                    # Money arriving is time-sensitive; a balance the user is waiting on
                    # should not be held in a batch.
                    'priority': 'high',
                    'notification': {'channel_id': 'mtag_transactions'},
                },
                'apns': {
                    'headers': {'apns-priority': '10'},
                    'payload': {'aps': {'sound': 'default'}},
                },
            }
        }
        try:
            response = requests.post(
                url, headers=headers, data=json.dumps(payload), timeout=_TIMEOUT
            )
        except requests.RequestException as exc:
            logger.warning('FCM send failed (network): %s', exc)
            continue

        if response.status_code == 200:
            delivered += 1
            DeviceToken.objects.filter(pk=token_id).update(
                last_used_at=timezone.now(), last_failure=''
            )
            continue

        reason = _error_reason(response)
        # 404 UNREGISTERED / 400 INVALID_ARGUMENT mean the token is permanently dead — the
        # app was uninstalled or the token rotated. Retrying it forever wastes a request per
        # event per device, so it is deactivated rather than left to rot.
        if response.status_code in (400, 404) and reason in (
            'UNREGISTERED',
            'INVALID_ARGUMENT',
        ):
            DeviceToken.objects.filter(pk=token_id).update(
                is_active=False, last_failure=reason
            )
            logger.info('Deactivated dead FCM token %s (%s)', token_id, reason)
        else:
            DeviceToken.objects.filter(pk=token_id).update(last_failure=reason)
            logger.warning('FCM send rejected: %s %s', response.status_code, reason)

    return delivered


def _error_reason(response) -> str:
    try:
        details = response.json().get('error', {})
        for item in details.get('details', []):
            if 'errorCode' in item:
                return str(item['errorCode'])
        return str(details.get('status', response.status_code))
    except (ValueError, AttributeError):
        return str(response.status_code)

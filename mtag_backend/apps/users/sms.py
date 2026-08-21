"""SMS delivery, behind a swappable backend.

Same seam as the payment gateways, for the same reason: the code that needs to send a
message should not know or care which provider is behind it, and an unconfigured provider
must fail HONESTLY rather than pretend it delivered something.

`SMS_BACKEND=console` (the default) writes the code to the Django log. That makes the whole
OTP flow testable today, before any gateway account exists — and because
`/auth/otp/request/` reports `delivery` back to the client, the app can say "check the
server log" in dev instead of claiming an SMS is on its way.
"""

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


class SmsSender:
    """Interface. `send` returns True only if the provider accepted the message."""

    #: Reported to the client so the UI can tell the truth about what just happened.
    name = 'none'

    def send(self, *, phone: str, message: str) -> bool:  # pragma: no cover - interface
        raise NotImplementedError


class ConsoleSmsSender(SmsSender):
    """Logs instead of sending. The default, and correct for dev and the LAN deployment.

    Deliberately logs at WARNING: a one-time code sitting in a log file is a real secret,
    and it should be conspicuous that this build is not delivering real SMS.
    """

    name = 'console'

    def send(self, *, phone: str, message: str) -> bool:
        logger.warning('[SMS:console] to %s: %s', phone, message)
        return True


class TwilioSmsSender(SmsSender):
    """Twilio REST. Requires TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_FROM.

    Untested against a live account — no credentials existed when this was written. It is
    here so the seam has a real second implementation and the swap is a settings change,
    not a rewrite.
    """

    name = 'twilio'

    def send(self, *, phone: str, message: str) -> bool:
        import requests

        sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
        token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
        sender = getattr(settings, 'TWILIO_FROM', '')
        if not (sid and token and sender):
            logger.error('Twilio selected but not configured; message dropped')
            return False
        try:
            response = requests.post(
                f'https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json',
                auth=(sid, token),
                data={'To': phone, 'From': sender, 'Body': message},
                timeout=10,
            )
        except Exception as exc:  # noqa: BLE001 - never propagate into a login path
            logger.error('Twilio send failed: %s', exc)
            return False
        if response.status_code >= 400:
            logger.error('Twilio rejected: %s %s', response.status_code, response.text[:200])
            return False
        return True


def get_sms_sender() -> SmsSender:
    backend = getattr(settings, 'SMS_BACKEND', 'console')
    return {'console': ConsoleSmsSender, 'twilio': TwilioSmsSender}.get(
        backend, ConsoleSmsSender
    )()

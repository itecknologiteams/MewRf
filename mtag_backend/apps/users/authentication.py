import logging

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

logger = logging.getLogger(__name__)


class CookieJWTAuthentication(JWTAuthentication):
    """Reads JWT from the httpOnly 'access_token' cookie, falls back to Bearer header.

    A cookie carrying an unusable token is treated as NOT AUTHENTICATED rather
    than as an error. That distinction matters: DRF runs authentication before
    permissions, so raising here returns 401 even on AllowAny endpoints — which
    locked users out of /auth/login/, the one endpoint they need in order to
    replace the bad token. Rotating SECRET_KEY invalidates every issued JWT, so
    every user would be locked out at once, with "Authentication required" and
    nothing pointing at cookies as the cause. Clearing browser cookies by hand
    was the only way back in.

    A token supplied explicitly in the Authorization header still raises, which
    is the conventional (and useful) behaviour: the caller chose to send it, so
    a malformed one should be reported rather than silently ignored.
    """

    def authenticate(self, request):
        header = self.get_header(request)

        if header is not None:
            # Explicit Bearer token — surface problems to the caller.
            raw_token = self.get_raw_token(header)
            if not raw_token:
                return None
            validated_token = self.get_validated_token(raw_token)
            return self.get_user(validated_token), validated_token

        cookie_val = request.COOKIES.get('access_token', '')
        if not cookie_val:
            return None

        try:
            validated_token = self.get_validated_token(cookie_val.encode())
            return self.get_user(validated_token), validated_token
        except (InvalidToken, TokenError) as exc:
            # Expired, malformed, or signed with a retired SECRET_KEY. Fall
            # through as anonymous: protected views still return 401 via the
            # permission layer, and login/refresh stay reachable so the client
            # can recover on its own.
            logger.debug("Ignoring unusable access_token cookie: %s", exc)
            return None

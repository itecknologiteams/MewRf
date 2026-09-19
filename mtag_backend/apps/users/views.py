import logging
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings as django_settings
from django.utils import timezone
from utils.response import success_response, error_response
from .serializers import (
    RegisterSerializer, LoginSerializer, UserDetailSerializer, UserListSerializer,
    SelfProfileUpdateSerializer,
)
from django.db.models import Q
from .models import OtpPurpose, User, UserRole
from .permissions import IsAdmin, IsOperator, is_privileged

logger = logging.getLogger(__name__)


class LoginRateThrottle(AnonRateThrottle):
    scope = 'login'


def _set_auth_cookies(response, access: str, refresh: str) -> None:
    # Follow SESSION_COOKIE_SECURE, NOT `not DEBUG`.
    #
    # config.settings.lan runs with DEBUG=False over plain HTTP on the toll LAN,
    # and deliberately sets SESSION_COOKIE_SECURE/CSRF_COOKIE_SECURE to False for
    # exactly that reason. Keying off DEBUG marked these cookies Secure, so the
    # browser silently discarded them: login returned 200, the cookie never
    # landed, the next request was unauthenticated, and the UI reported "invalid
    # phone number or password". Nobody could log into master or any booth.
    #
    # production.py sets SESSION_COOKIE_SECURE=True, so HTTPS deployments still
    # get Secure cookies. Falls back to the old behaviour if the setting is absent.
    is_secure = getattr(
        django_settings, 'SESSION_COOKIE_SECURE', not django_settings.DEBUG
    )
    jwt_settings = django_settings.SIMPLE_JWT
    access_max_age = int(jwt_settings['ACCESS_TOKEN_LIFETIME'].total_seconds())
    refresh_max_age = int(jwt_settings['REFRESH_TOKEN_LIFETIME'].total_seconds())
    response.set_cookie('access_token', access, max_age=access_max_age,
                        httponly=True, samesite='Lax', secure=is_secure, path='/')
    response.set_cookie('refresh_token', refresh, max_age=refresh_max_age,
                        httponly=True, samesite='Lax', secure=is_secure, path='/')


def _clear_auth_cookies(response) -> None:
    response.delete_cookie('access_token', path='/')
    response.delete_cookie('refresh_token', path='/')


class RegisterView(APIView):
    """Create a consumer account.

    AllowAny at the DRF layer, then gated in the handler, because the two callers
    need different answers:

      - the operator portal's Registration page creates the tag holder while
        fitting their tag, authenticated as an operator. That must keep working.
      - an anonymous caller is self-signup, and there is NO verification step
        here: no OTP, no proof the phone belongs to the caller. Left open, anyone
        could create `user` rows against arbitrary phone numbers — including a
        number that a booth will later try to register, and including numbers
        belonging to real people. Real accounts are created at a booth.

    So anonymous registration is off unless USER_SELF_REGISTRATION_ENABLED is
    set, which should only be turned on once phone-OTP verification exists.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        self_signup_allowed = getattr(
            django_settings, 'USER_SELF_REGISTRATION_ENABLED', False
        )
        if not (is_privileged(request.user) or self_signup_allowed):
            return error_response(
                "Self-registration is not available. ME-Tag accounts are created "
                "at a toll booth — please visit a booth or contact support.",
                status_code=403,
            )
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            logger.info("New user registered: %s", user.phone)
            return success_response(
                data=UserDetailSerializer(user).data,
                message="Registration successful",
                status_code=201
            )
        return error_response("Registration failed", errors=serializer.errors)


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            access = data.pop('access')
            refresh = data.pop('refresh')
            response = success_response(data=data, message="Login successful")
            _set_auth_cookies(response, access, refresh)
            return response
        return error_response("Login failed", errors=serializer.errors, status_code=401)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token_str = request.COOKIES.get('refresh_token') or request.data.get('refresh', '')
        if refresh_token_str:
            try:
                token = RefreshToken(refresh_token_str)
                token.blacklist()
            except Exception:
                pass
        response = success_response(message="Logged out successfully")
        _clear_auth_cookies(response)
        return response


class TokenRefreshCookieView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        from rest_framework_simplejwt.serializers import TokenRefreshSerializer
        refresh_token_str = request.COOKIES.get('refresh_token')
        if not refresh_token_str:
            return error_response("No refresh token", status_code=401)
        try:
            serializer = TokenRefreshSerializer(data={'refresh': refresh_token_str})
            serializer.is_valid(raise_exception=True)
            access = serializer.validated_data['access']
            new_refresh = serializer.validated_data.get('refresh', refresh_token_str)
            response = success_response(data={'detail': 'Token refreshed'})
            _set_auth_cookies(response, access, new_refresh)
            return response
        except Exception:
            response = error_response("Session expired. Please log in again.", status_code=401)
            _clear_auth_cookies(response)
            return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return success_response(data=UserDetailSerializer(request.user).data)

    def patch(self, request):
        # SelfProfileUpdateSerializer, not UserDetailSerializer — see its
        # docstring. Unknown keys are ignored by DRF rather than rejected, so an
        # old client still sending `phone` gets a 200 with the phone unchanged
        # instead of a confusing validation error.
        serializer = SelfProfileUpdateSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            user = serializer.save()
            return success_response(
                data=UserDetailSerializer(user).data, message="Profile updated"
            )
        return error_response("Update failed", errors=serializer.errors)


class AdminUserListView(APIView):
    """The admin Users page, and the owner lookup on the ME-Tag Registration page.

    Operators get the lookup only: a search term is required, so a booth account
    cannot use this to pull every consumer's name and phone number in one call.

    search/role/status used to be ignored, so the registration lookup took the
    newest account in the system as the "found" owner whatever phone was typed.
    """
    permission_classes = [IsOperator]

    def get(self, request):
        search = request.query_params.get('search', '').strip()
        if request.user.user_role != UserRole.ADMIN and not search:
            return error_response("A search term is required", status_code=403)

        users = User.objects.all().order_by('-id')
        if search:
            users = users.filter(Q(phone__icontains=search) | Q(full_name__icontains=search))
        role = request.query_params.get('role')
        if role:
            users = users.filter(user_role=role)
        user_status = request.query_params.get('status')
        if user_status:
            users = users.filter(status=user_status)
        serializer = UserListSerializer(users, many=True)
        return success_response(data=serializer.data)


class AdminUserDetailView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
            return success_response(data=UserDetailSerializer(user).data)
        except User.DoesNotExist:
            return error_response("User not found", status_code=404)

    def patch(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
            serializer = UserDetailSerializer(user, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return success_response(data=serializer.data, message="User updated")
            return error_response("Update failed", errors=serializer.errors)
        except User.DoesNotExist:
            return error_response("User not found", status_code=404)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        old_password = request.data.get('old_password', '')
        new_password = request.data.get('new_password', '')

        if not old_password or not new_password:
            return error_response("old_password and new_password are required")
        if not request.user.check_password(old_password):
            return error_response("Current password is incorrect", status_code=400)
        if len(new_password) < 8:
            return error_response("New password must be at least 8 characters")

        request.user.set_password(new_password)
        # Stamped here too, not only in the OTP flow: someone who changes their password
        # through the app has demonstrably chosen one, and /auth/phone-status/ must not
        # then send them back through verification.
        request.user.password_set_at = timezone.now()
        request.user.save(update_fields=['password', 'password_set_at'])
        logger.info("Password changed for user %s", request.user.phone)
        return success_response(message="Password changed successfully")


# ── First-time password setup via phone OTP ──────────────────────────────────
#
# Fills the gap that made the consumer app unusable for a real customer: booths create the
# account when the tag is fitted, but nobody ever hands the customer a password. These three
# endpoints let the holder of the registered phone set one.
#
# Deliberately NOT signup. An unknown number is turned away, so this cannot mint accounts
# with no tag behind them — which is why USER_SELF_REGISTRATION_ENABLED can stay off.


class OtpRateThrottle(AnonRateThrottle):
    """Codes cost money to send and are a spam vector aimed at someone else's phone."""
    scope = 'otp'


def _otp_purpose(request):
    """The requested OTP purpose, or None if it is not one we issue.

    Defaults to setup so an older client that sends no `purpose` keeps working unchanged.
    An unrecognised value is REFUSED rather than silently defaulted: quietly treating
    `purpose=reset` from a typo as a setup would skip session revocation, which is the one
    thing a reset does that a setup does not.
    """
    raw = (request.data.get('purpose') or OtpPurpose.PASSWORD_SETUP).strip().lower()
    return raw if raw in {choice for choice, _ in OtpPurpose.choices} else None


def _bad_purpose():
    return error_response(
        'Unknown verification purpose.',
        errors={'purpose': [c for c, _ in OtpPurpose.choices]},
        status_code=400,
    )


class OtpRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [OtpRateThrottle]

    def post(self, request):
        from .otp_service import request_code

        # `device_token` is IGNORED unless OTP_PUSH_TO_REQUESTING_DEVICE is on, which is a
        # dev-only setting that production settings refuse to boot with. Accepting the field
        # unconditionally keeps the client identical across environments; what changes is
        # whether the server is willing to act on it.
        purpose = _otp_purpose(request)
        if purpose is None:
            return _bad_purpose()

        result = request_code(
            request.data.get('phone', ''),
            device_token=(request.data.get('device_token') or '').strip(),
            purpose=purpose,
        )
        if result['sent']:
            return success_response(
                data={
                    'delivery': result['delivery'],
                    # Every channel that actually carried the code, so the app can say
                    # where to look instead of guessing. A holder already signed in on this
                    # handset gets it as a notification; a fresh install gets an SMS.
                    'channels': result.get('channels', []),
                    'pushed_to_devices': result.get('pushed_to', 0),
                    'purpose': purpose,
                },
                message='Verification code sent',
            )

        # Reported plainly — see request_code for why enumeration is the right trade here.
        return error_response(
            {
                'no_account': 'No ME-Tag account exists for this number. Accounts are '
                              'created at a toll booth when your tag is fitted.',
                'blocked': 'This account is blocked. Contact support.',
            }.get(result['reason'], 'Could not send the verification code.'),
            errors={'reason': result['reason']},
            status_code=404 if result['reason'] == 'no_account' else 400,
        )


class OtpVerifyView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [OtpRateThrottle]

    def post(self, request):
        from .otp_service import verify_code

        purpose = _otp_purpose(request)
        if purpose is None:
            return _bad_purpose()

        result = verify_code(
            request.data.get('phone', ''),
            request.data.get('code', ''),
            purpose=purpose,
        )
        if result['ok']:
            return success_response(
                data={'token': result['token']}, message='Verified'
            )
        return error_response(
            {
                'expired': 'That code has expired. Request a new one.',
                'too_many_attempts': 'Too many incorrect attempts. Request a new code.',
                'not_found': 'Request a verification code first.',
            }.get(result['reason'], 'That code is not correct.'),
            errors={
                'reason': result['reason'],
                **(
                    {'attempts_left': result['attempts_left']}
                    if 'attempts_left' in result
                    else {}
                ),
            },
            status_code=400,
        )


class OtpSetPasswordView(APIView):
    """Sets the password AND signs the user in, so they land on the dashboard."""

    permission_classes = [AllowAny]
    throttle_classes = [OtpRateThrottle]

    def post(self, request):
        from rest_framework_simplejwt.tokens import RefreshToken

        from .otp_service import set_password_with_token

        password = request.data.get('new_password', '')
        confirm = request.data.get('confirm_password', password)

        if len(password) < 8:
            return error_response(
                'Password must be at least 8 characters',
                errors={'new_password': ['Password must be at least 8 characters']},
            )
        if password != confirm:
            return error_response(
                'Passwords do not match',
                errors={'confirm_password': ['Passwords do not match']},
            )

        purpose = _otp_purpose(request)
        if purpose is None:
            return _bad_purpose()

        # Revocation happens inside this call, BEFORE the new session is minted below — so
        # the token this response hands back is not caught by the blacklist it just wrote.
        result = set_password_with_token(
            request.data.get('token', ''), password, purpose=purpose
        )
        if not result['ok']:
            return error_response(
                {
                    'token_expired': 'That took too long. Verify your number again.',
                    'token_invalid': 'Verification failed. Start again.',
                }.get(result['reason'], 'Could not set your password.'),
                errors={'reason': result['reason']},
                status_code=400,
            )

        # Signed in immediately: making someone type the password they just chose, on the
        # very next screen, is friction with no security value.
        user = result['user']
        user.last_login_at = timezone.now()
        user.save(update_fields=['last_login_at'])
        refresh = RefreshToken.for_user(user)
        response = success_response(
            data={
                'user_id': user.id,
                'uuid': str(user.uuid),
                'full_name': user.full_name,
                'phone': user.phone,
                # How many other sessions this reset ended, so the app can say
                # "you have been signed out on your other devices" rather than leaving the
                # user to discover it.
                'sessions_revoked': result.get('sessions_revoked', 0),
                'role': user.user_role,
            },
            message='Password set',
        )
        _set_auth_cookies(response, str(refresh.access_token), str(refresh))
        return response


class PhoneStatusView(APIView):
    """Does this number have an account, and has its holder ever chosen a password?

    Called by the app before requesting a code, so somebody who already has a password is
    sent to the login screen instead of being handed a verification code they do not need.

    `has_password` reports `password_set_at`, NOT `has_usable_password()`. Every
    booth-created account is given a random password it is never told, so Django's own flag
    is True for exactly the people who still need the setup flow — see User.password_set_at.

    Discloses whether a number is registered, which is the same disclosure
    /auth/otp/request/ already makes, and for the same reason: these accounts are created at
    a booth from a number the operator already holds, so it is not a secret worth protecting
    — while hiding it would leave the app unable to route the user to the right screen.
    """

    permission_classes = [AllowAny]
    throttle_classes = [OtpRateThrottle]

    def post(self, request):
        from .otp_service import normalize_phone

        phone = normalize_phone(request.data.get('phone', ''))
        user = User.objects.filter(phone=phone).only(
            'status', 'password_set_at', 'user_role'
        ).first()

        return success_response(
            data={
                'exists': user is not None,
                'has_password': user is not None and user.password_set_at is not None,
                'blocked': user is not None and user.status == 'blocked',
                # The consumer app refuses staff logins, so it can say so up front rather
                # than after a successful sign-in.
                'is_staff_account': user is not None
                and user.user_role in ('admin', 'operator'),
            }
        )

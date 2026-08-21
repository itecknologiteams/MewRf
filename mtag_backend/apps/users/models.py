import uuid
from datetime import timedelta
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from .managers import UserManager


class UserRole(models.TextChoices):
    USER = 'user', 'User'
    ADMIN = 'admin', 'Admin'
    OPERATOR = 'operator', 'Operator'


class UserStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    INACTIVE = 'inactive', 'Inactive'
    BLOCKED = 'blocked', 'Blocked'


class User(AbstractBaseUser, PermissionsMixin):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    full_name = models.CharField(max_length=100)
    cnic = models.CharField(max_length=15, unique=True, null=True, blank=True)
    phone = models.CharField(max_length=20, unique=True)
    user_role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.USER)
    status = models.CharField(max_length=20, choices=UserStatus.choices, default=UserStatus.ACTIVE)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='created_users'
    )
    last_login_at = models.DateTimeField(null=True, blank=True)

    #: When the USER themselves chose their password. Null means they never have.
    #:
    #: `has_usable_password()` cannot answer this. Every booth-created account is given a
    #: RANDOM 12-character password it is never told (see CashTopupView and
    #: RegisterSerializer), so Django reports "has a password" for precisely the people who
    #: still need to set one. This field is the only honest signal, and it is what
    #: /auth/phone-status/ reports so the app can route someone to login instead of sending
    #: a pointless code.
    #:
    #: Set by the OTP setup flow and by change-password; never by account creation.
    password_set_at = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = ['full_name']

    class Meta:
        db_table = 'users'
        indexes = [
            models.Index(fields=['phone']),
            models.Index(fields=['cnic']),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.phone})"


class OtpPurpose(models.TextChoices):
    """Why a code was issued. A code minted for one purpose must never satisfy another."""

    #: First password, for an account created at a booth that has never had one.
    PASSWORD_SETUP = 'password_setup', 'Password setup'

    #: Forgot password. Same proof — possession of the phone — but a different outcome:
    #: the holder already had a password, so completing this REVOKES every existing
    #: session. Someone resetting because their account was taken over would otherwise
    #: hand the intruder a password change and leave their live session untouched.
    PASSWORD_RESET = 'password_reset', 'Password reset'


class PhoneOtp(models.Model):
    """A one-time code sent to a phone, for first-time password setup and reset.

    ## Why this exists

    M-Tag accounts are created at a booth when the tag is fitted, using the customer's
    phone number — but nobody ever gives that customer a password. Before this, there was
    no way for a tag holder to get into the app at all, and no reset path either.

    This proves the caller holds the phone the booth registered, and lets them set a
    password on the account that already exists. It is NOT a signup: an unknown number is
    turned away, so the app cannot mint accounts with no tag behind them.

    ## Security properties

    * **The code is hashed, never stored.** A dump of this table must not let anyone walk
      into accounts. Same reasoning as passwords.
    * **Short expiry** and a **hard attempt cap** — a 6-digit code is 10^6, which is
      brute-forceable in minutes if you let someone try.
    * **Single use.** `consumed_at` is set the moment it verifies.
    * Issuing a new code **invalidates the previous one** for that phone, so a code
      intercepted earlier cannot be replayed after the user asks for another.
    """

    phone = models.CharField(max_length=20, db_index=True)
    code_hash = models.CharField(max_length=128)
    purpose = models.CharField(
        max_length=32, choices=OtpPurpose.choices, default=OtpPurpose.PASSWORD_SETUP
    )

    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)

    # Counted against MAX_ATTEMPTS. Kept on the row rather than in cache so a restart
    # cannot reset an attacker's budget.
    attempts = models.PositiveSmallIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    #: A code is good for five minutes. Long enough for a slow SMS, short enough that an
    #: intercepted code is usually already dead.
    LIFETIME = timedelta(minutes=5)

    #: Wrong guesses before the code is burned.
    MAX_ATTEMPTS = 5

    class Meta:
        db_table = 'phone_otps'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['phone', '-created_at'])]

    def __str__(self):
        return f'{self.phone} {self.purpose} ({"used" if self.consumed_at else "open"})'

    @property
    def is_expired(self) -> bool:
        from django.utils import timezone
        return timezone.now() >= self.expires_at

    @property
    def is_usable(self) -> bool:
        return (
            self.consumed_at is None
            and not self.is_expired
            and self.attempts < self.MAX_ATTEMPTS
        )

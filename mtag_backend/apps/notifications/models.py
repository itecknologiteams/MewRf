from django.db import models


class DevicePlatform(models.TextChoices):
    ANDROID = 'android', 'Android'
    IOS = 'ios', 'iOS'


class DeviceToken(models.Model):
    """An FCM registration token for one install of the consumer app.

    One row per (user, token). A user legitimately has several: a phone and a tablet, or the
    same phone before and after a reinstall.

    `token` is unique across the table, not per user, because FCM reissues a token to a
    DIFFERENT user when a device is handed on — if two rows could hold the same token, one
    person's balance notifications would land on someone else's phone. Registering a token
    that already exists REASSIGNS it rather than duplicating it.
    """

    user = models.ForeignKey(
        'users.User', on_delete=models.CASCADE, related_name='device_tokens'
    )
    token = models.CharField(max_length=255, unique=True)
    platform = models.CharField(
        max_length=10, choices=DevicePlatform.choices, default=DevicePlatform.ANDROID
    )

    # Cleared when FCM reports the token as permanently gone (UNREGISTERED /
    # INVALID_ARGUMENT). Kept as a row rather than deleted so a reinstall can reactivate it
    # and so the failure is visible when someone asks why a user stopped getting alerts.
    is_active = models.BooleanField(default=True)
    last_failure = models.CharField(max_length=120, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'device_tokens'
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['token']),
        ]

    def __str__(self):
        return f'{self.user_id} {self.platform} {self.token[:12]}…'

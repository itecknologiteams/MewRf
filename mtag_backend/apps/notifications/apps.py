from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.notifications'

    def ready(self):
        # Importing for the side effect of registering the post_save receivers. Signals are
        # how this app hooks money events WITHOUT touching the 16 places that create a
        # Transaction — see signals.py for why that matters.
        from . import signals  # noqa: F401

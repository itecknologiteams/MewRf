from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from rest_framework.permissions import AllowAny, IsAdminUser

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/auth/', include('apps.users.urls')),
    path('api/v1/vehicles/', include('apps.vehicles.urls')),
    path('api/v1/accounts/', include('apps.accounts.urls')),
    path('api/v1/tolls/', include('apps.tolls.urls')),
    path('api/v1/payments/', include('apps.payments.urls')),
    path('api/v1/notifications/', include('apps.notifications.urls')),

    # The booth console — a diagnostics page a booth serves about ITSELF, at
    # http://<booth-lan-ip>:8000/booth/. Present on master too, since master
    # runs the same code; it detects the absence of rfid_config.ini and says so
    # rather than rendering a lane that is not there.
    path('booth/', include('apps.tolls.booth_urls')),
]

# ── API documentation ─────────────────────────────────────────────────────────
#
# Appended conditionally rather than always: this API is reachable from the public
# internet, and a browsable schema is a complete map of the attack surface — including
# every operator and admin path. API_DOCS_PUBLIC must be set deliberately.
if getattr(settings, 'API_DOCS_ENABLED', False):
    from drf_spectacular.views import (
        SpectacularAPIView,
        SpectacularRedocView,
        SpectacularSwaggerView,
    )

    if getattr(settings, 'API_DOCS_PUBLIC', False):
        permissions = [AllowAny]
    else:
        # Admin-only by default. Note this needs a session or a valid auth cookie, so log
        # in through /admin/ or the app first — the docs are not a way IN, they are a
        # reference for someone already trusted.
        permissions = [IsAdminUser]

    urlpatterns += [
        path(
            'api/schema/',
            SpectacularAPIView.as_view(permission_classes=permissions),
            name='schema',
        ),
        path(
            'api/docs/',
            SpectacularSwaggerView.as_view(
                url_name='schema', permission_classes=permissions
            ),
            name='swagger-ui',
        ),
        path(
            'api/redoc/',
            SpectacularRedocView.as_view(
                url_name='schema', permission_classes=permissions
            ),
            name='redoc',
        ),
    ]

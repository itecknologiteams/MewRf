from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_role == 'admin'


class IsOperator(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_role in ('admin', 'operator')


class IsOwnerOrAdmin(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.user_role == 'admin':
            return True
        return getattr(obj, 'owner', None) == request.user


# ── Consumer scoping ─────────────────────────────────────────────────────────
# The consumer app (M-Tag User App) authenticates as a plain `user`, and every
# detail endpoint it reads takes an id in the path: /accounts/vehicle/<id>/,
# /accounts/<id>/transactions/, /tolls/trips/<id>/, /vehicles/<id>/. Those views
# were `IsAuthenticated` with no owner check, so any logged-in account could read
# any other consumer's balance, transactions and trip history by incrementing the
# id. These helpers close that by filtering the queryset down to what the caller
# owns; operators and admins keep the cross-account access they already had.
#
# Filtering (rather than fetching then comparing) is deliberate: a non-owned id
# then produces the view's existing DoesNotExist -> 404 path, so the response is
# identical whether the row is absent or simply not yours. A 403 would confirm
# that the id exists, which is exactly the enumeration this is meant to prevent.

def is_privileged(user) -> bool:
    """True for operators and admins — the roles allowed cross-account reads."""
    return getattr(user, 'user_role', None) in ('admin', 'operator')


def scope_to_owner(queryset, user, owner_field='owner'):
    """Restrict `queryset` to rows the consumer owns; pass privileged users through.

    `owner_field` is the ORM path from the model to users.User, e.g. 'owner' on
    Vehicle, 'user' on Account, 'vehicle__owner' on Tag/TollTrip.
    """
    if is_privileged(user):
        return queryset
    return queryset.filter(**{owner_field: user})

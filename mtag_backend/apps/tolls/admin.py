from django.contrib import admin
from .models import FareMatrix, Plaza, TollLane, TollRate, TollTrip


class TollLaneInline(admin.TabularInline):
    model = TollLane
    extra = 0


@admin.register(Plaza)
class PlazaAdmin(admin.ModelAdmin):
    list_display = ['display_id', 'name', 'is_active']
    ordering = ['plaza_id']
    search_fields = ['name', 'plaza_id']
    inlines = [TollLaneInline]

    @admin.display(ordering='plaza_id', description='Plaza ID')
    def display_id(self, obj):
        # Zero-padded to match the operator's numbering ("001", not "1").
        return obj.display_id


@admin.register(TollRate)
class TollRateAdmin(admin.ModelAdmin):
    """LEGACY — nothing prices from this table any more.

    Fares live in FareMatrix (below). Kept visible so historical rate rows can
    still be inspected, but made read-only: an operator editing here would see
    it save and have zero effect on what any vehicle is charged.
    """
    list_display = ['entry_plaza', 'exit_plaza', 'vehicle_type', 'rate', 'effective_from']
    list_filter = ['vehicle_type', 'entry_plaza', 'exit_plaza']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(TollTrip)
class TollTripAdmin(admin.ModelAdmin):
    list_display = ['vehicle', 'entry_plaza', 'exit_plaza', 'charge_amount', 'status', 'entry_time']
    list_filter = ['status']
    search_fields = ['vehicle__plate_number']
    readonly_fields = ['entry_time', 'exit_time']


@admin.register(FareMatrix)
class FareMatrixAdmin(admin.ModelAdmin):
    """Operator-editable fares. This is what ExitService actually charges."""
    list_display = ['from_plaza', 'to_plaza', 'category', 'fare', 'updated_at']
    list_filter = ['category', 'from_plaza', 'to_plaza']
    list_editable = ['fare']
    list_select_related = ['from_plaza', 'to_plaza', 'category']
    ordering = ['from_plaza__plaza_id', 'to_plaza__plaza_id', 'category__category_index']

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # ExitService caches fares for 10 minutes; drop it so an edited fare
        # takes effect on the next vehicle instead of up to 10 minutes later.
        from apps.tolls.services import invalidate_rate_cache
        invalidate_rate_cache()

from django.contrib import admin
from .models import Vehicle, Tag, VehicleCategory, TagAssignment


class TagInline(admin.StackedInline):
    model = Tag
    extra = 0


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ['plate_number', 'owner', 'vehicle_type', 'status', 'registered_at']
    list_filter = ['vehicle_type', 'status']
    search_fields = ['plate_number', 'owner__phone']
    inlines = [TagInline]


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['tag_serial', 'vehicle', 'status', 'expiry_date', 'last_scanned_at']
    list_filter = ['status']
    search_fields = ['tag_serial']


@admin.register(VehicleCategory)
class VehicleCategoryAdmin(admin.ModelAdmin):
    list_display = ['category_index', 'code', 'name', 'is_active']
    ordering = ['category_index']
    search_fields = ['code', 'name']


@admin.register(TagAssignment)
class TagAssignmentAdmin(admin.ModelAdmin):
    """Tag installation history — which vehicle, from when, until when."""
    list_display = ['tag_serial', 'plate_number', 'assigned_at', 'removed_at', 'removed_reason']
    list_filter = ['assigned_at', 'removed_at']
    search_fields = ['tag_serial', 'plate_number']
    date_hierarchy = 'assigned_at'
    readonly_fields = ['created_at', 'updated_at']

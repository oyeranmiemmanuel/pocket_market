from django.contrib import admin

from .models import (
    CollectionBatch,
    DeliveryTask,
    Package,
    PackageItem,
    PickupTask,
    RiderAssignment,
    RouteActivity,
    SellerFulfillment,
)


class PackageItemInline(admin.TabularInline):
    model = PackageItem
    extra = 0


class PickupTaskInline(admin.TabularInline):
    model = PickupTask
    extra = 0
    fields = ("status", "rider", "batch", "requested_at", "collected_at")
    readonly_fields = ("requested_at",)


@admin.register(SellerFulfillment)
class SellerFulfillmentAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "seller", "status", "ready_at", "created_at")
    list_filter = ("status",)
    search_fields = ("order__reference", "seller__store_name")
    autocomplete_fields = ["order", "seller"]


@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ("reference", "fulfillment", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("reference",)
    inlines = [PackageItemInline, PickupTaskInline]


@admin.register(PickupTask)
class PickupTaskAdmin(admin.ModelAdmin):
    list_display = ("id", "package", "status", "rider", "batch", "collected_at")
    list_filter = ("status",)
    search_fields = ("package__reference",)


@admin.register(CollectionBatch)
class CollectionBatchAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "rider", "assigned_at", "completed_at")
    list_filter = ("status",)
    inlines = [PickupTaskInline]


@admin.register(RiderAssignment)
class RiderAssignmentAdmin(admin.ModelAdmin):
    list_display = ("id", "rider", "assigned_to", "status", "offered_at")
    list_filter = ("status",)


@admin.register(DeliveryTask)
class DeliveryTaskAdmin(admin.ModelAdmin):
    list_display = ("id", "delivery", "status", "rider", "delivered_at")
    list_filter = ("status",)


@admin.register(RouteActivity)
class RouteActivityAdmin(admin.ModelAdmin):
    list_display = ("id", "batch", "sequence", "activity_type", "status")
    list_filter = ("activity_type", "status")
from django.contrib import admin

from apps.core.admin_badges import status_badge

from .models import Order, OrderItem, ShippingAddress


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["product", "product_name", "unit_price", "quantity", "seller", "fulfillment_status"]


class ShippingAddressInline(admin.StackedInline):
    model = ShippingAddress
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["reference", "full_name", "email", "status_display", "total", "created_at"]
    list_filter = ["status", "delivery_method", "created_at"]
    search_fields = ["reference", "email", "full_name"]
    readonly_fields = ["reference", "subtotal", "shipping_fee", "total", "created_at", "updated_at"]
    inlines = [OrderItemInline, ShippingAddressInline]
    list_per_page = 25
    date_hierarchy = "created_at"

    fieldsets = (
        ("Order", {
            "fields": ("reference", "user", "status", "delivery_method"),
        }),
        ("Customer", {
            "fields": ("full_name", "email", "phone"),
        }),
        ("Amounts", {
            "fields": ("subtotal", "shipping_fee", "total"),
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description="Status", ordering="status")
    def status_display(self, obj):
        return status_badge(obj.get_status_display(), obj.status)

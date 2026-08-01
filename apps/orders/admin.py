from django.contrib import admin

from .models import Order, OrderItem, ShippingAddress


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["product", "product_name", "unit_price", "quantity"]


class ShippingAddressInline(admin.StackedInline):
    model = ShippingAddress
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["reference", "full_name", "email", "status", "total", "created_at"]
    list_filter = ["status"]
    search_fields = ["reference", "email", "full_name"]
    inlines = [OrderItemInline, ShippingAddressInline]

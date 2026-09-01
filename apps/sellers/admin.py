from django.contrib import admin

from .models import SellerEarning, SellerProfile
from .services import (
    approve_seller,
    cancel_seller_earning,
    confirm_seller_earning,
    mark_seller_earning_available,
    reject_seller,
    reverse_seller_earning,
    suspend_seller,
)


@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    list_display = [
        "store_name", "user", "status", "commission_rate",
        "total_earnings", "available_earnings", "created_at",
    ]
    list_filter = ["status"]
    search_fields = ["store_name", "user__username", "user__email", "business_email"]
    readonly_fields = ["reviewed_at", "reviewed_by"]
    actions = ["approve_sellers", "reject_sellers", "suspend_sellers"]

    @admin.action(description="Approve selected sellers")
    def approve_sellers(self, request, queryset):
        for profile in queryset:
            approve_seller(profile=profile, reviewed_by=request.user)
        self.message_user(request, f"Approved {queryset.count()} seller(s).")

    @admin.action(description="Reject selected sellers")
    def reject_sellers(self, request, queryset):
        for profile in queryset:
            reject_seller(profile=profile, reviewed_by=request.user, reason="Rejected via admin bulk action.")
        self.message_user(request, f"Rejected {queryset.count()} seller(s).")

    @admin.action(description="Suspend selected sellers")
    def suspend_sellers(self, request, queryset):
        for profile in queryset:
            suspend_seller(profile=profile, reviewed_by=request.user, reason="Suspended via admin bulk action.")
        self.message_user(request, f"Suspended {queryset.count()} seller(s).")


@admin.register(SellerEarning)
class SellerEarningAdmin(admin.ModelAdmin):
    """
    Phase 8. Earnings are system-generated (never created/edited by hand -
    see apps.sellers.services.record_seller_earning), so this is
    read-only except for the status-transition actions below, which go
    through the same services.py functions the rest of the codebase uses
    rather than letting an admin free-edit `status` directly.
    """

    list_display = [
        "seller", "order", "order_item", "order_amount",
        "earning_amount", "status", "created_at",
    ]
    list_filter = ["status", "created_at"]
    search_fields = ["seller__store_name", "order__reference"]
    readonly_fields = [
        "seller", "order", "order_item", "order_amount",
        "platform_commission_rate", "platform_commission_amount",
        "affiliate_commission_amount", "earning_amount", "reversal_of",
    ]
    actions = ["confirm_earnings", "mark_available", "cancel_earnings", "reverse_earnings"]

    def has_add_permission(self, request):
        return False

    @admin.action(description="Confirm selected earnings (pending -> confirmed)")
    def confirm_earnings(self, request, queryset):
        count = 0
        for earning in queryset.filter(status="pending"):
            confirm_seller_earning(earning=earning)
            count += 1
        self.message_user(request, f"Confirmed {count} earning(s).")

    @admin.action(description="Mark selected earnings available for payout")
    def mark_available(self, request, queryset):
        count = 0
        for earning in queryset.filter(status="confirmed"):
            mark_seller_earning_available(earning=earning)
            count += 1
        self.message_user(request, f"Marked {count} earning(s) available.")

    @admin.action(description="Cancel selected earnings")
    def cancel_earnings(self, request, queryset):
        count = 0
        for earning in queryset.exclude(status__in=["paid", "reversed"]):
            cancel_seller_earning(earning=earning, reason="Cancelled via admin bulk action.")
            count += 1
        self.message_user(request, f"Cancelled {count} earning(s).")

    @admin.action(description="Reverse selected earnings (e.g. after a refund)")
    def reverse_earnings(self, request, queryset):
        count = 0
        for earning in queryset.exclude(status__in=["cancelled", "reversed"]):
            reverse_seller_earning(earning=earning, reason="Reversed via admin bulk action.")
            count += 1
        self.message_user(request, f"Reversed {count} earning(s).")
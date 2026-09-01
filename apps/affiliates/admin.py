from django.contrib import admin

from .models import AffiliateClick, AffiliateCommission, AffiliateLink, AffiliateProfile
from .services import (
    approve_affiliate,
    cancel_commission,
    confirm_commission,
    mark_commission_available,
    reject_affiliate,
    reverse_commission,
    suspend_affiliate,
)


@admin.register(AffiliateProfile)
class AffiliateProfileAdmin(admin.ModelAdmin):
    list_display = [
        "affiliate_code", "user", "status", "commission_rate",
        "total_earnings", "available_earnings", "created_at",
    ]
    list_filter = ["status"]
    search_fields = ["affiliate_code", "user__username", "user__email"]
    readonly_fields = ["affiliate_code", "reviewed_at", "reviewed_by"]
    actions = ["approve_affiliates", "reject_affiliates", "suspend_affiliates"]

    @admin.action(description="Approve selected affiliates")
    def approve_affiliates(self, request, queryset):
        for profile in queryset:
            approve_affiliate(profile=profile, reviewed_by=request.user)
        self.message_user(request, f"Approved {queryset.count()} affiliate(s).")

    @admin.action(description="Reject selected affiliates")
    def reject_affiliates(self, request, queryset):
        for profile in queryset:
            reject_affiliate(profile=profile, reviewed_by=request.user, reason="Rejected via admin bulk action.")
        self.message_user(request, f"Rejected {queryset.count()} affiliate(s).")

    @admin.action(description="Suspend selected affiliates")
    def suspend_affiliates(self, request, queryset):
        for profile in queryset:
            suspend_affiliate(profile=profile, reviewed_by=request.user, reason="Suspended via admin bulk action.")
        self.message_user(request, f"Suspended {queryset.count()} affiliate(s).")


@admin.register(AffiliateLink)
class AffiliateLinkAdmin(admin.ModelAdmin):
    list_display = ["referral_code", "affiliate", "product", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["referral_code", "affiliate__affiliate_code", "product__name"]
    readonly_fields = ["referral_code"]


@admin.register(AffiliateClick)
class AffiliateClickAdmin(admin.ModelAdmin):
    """
    Read-only in admin - clicks are a log, not something staff edit.
    Lets an admin spot suspicious activity (spec section 10: "view
    suspicious activity") - e.g. one session_key with an unusually high
    click count for one affiliate.
    """

    list_display = ["affiliate", "product", "session_key", "converted", "created_at"]
    list_filter = ["converted", "created_at"]
    search_fields = ["affiliate__affiliate_code", "product__name", "session_key"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(AffiliateCommission)
class AffiliateCommissionAdmin(admin.ModelAdmin):
    """
    Phase 7. Commissions are system-generated (never created/edited by
    hand - see record_conversion_for_order), so this is read-only except
    for the status-transition actions below, which go through the same
    services.py functions the rest of the codebase uses rather than
    letting an admin free-edit `status` directly.
    """

    list_display = [
        "affiliate", "order", "order_item", "commission_rate",
        "commission_amount", "status", "created_at",
    ]
    list_filter = ["status", "created_at"]
    search_fields = ["affiliate__affiliate_code", "order__reference"]
    readonly_fields = [
        "affiliate", "order", "order_item", "affiliate_link",
        "order_amount", "commission_rate", "commission_amount", "reversal_of",
    ]
    actions = [
        "confirm_commissions", "mark_available", "cancel_commissions", "reverse_commissions",
    ]

    def has_add_permission(self, request):
        return False

    @admin.action(description="Confirm selected commissions (pending -> confirmed)")
    def confirm_commissions(self, request, queryset):
        count = 0
        for commission in queryset.filter(status="pending"):
            confirm_commission(commission=commission)
            count += 1
        self.message_user(request, f"Confirmed {count} commission(s).")

    @admin.action(description="Mark selected commissions available for payout")
    def mark_available(self, request, queryset):
        count = 0
        for commission in queryset.filter(status="confirmed"):
            mark_commission_available(commission=commission)
            count += 1
        self.message_user(request, f"Marked {count} commission(s) available.")

    @admin.action(description="Cancel selected commissions")
    def cancel_commissions(self, request, queryset):
        count = 0
        for commission in queryset.exclude(status__in=["paid", "reversed"]):
            cancel_commission(commission=commission, reason="Cancelled via admin bulk action.")
            count += 1
        self.message_user(request, f"Cancelled {count} commission(s).")

    @admin.action(description="Reverse selected commissions (e.g. after a refund)")
    def reverse_commissions(self, request, queryset):
        count = 0
        for commission in queryset.exclude(status__in=["cancelled", "reversed"]):
            reverse_commission(commission=commission, reason="Reversed via admin bulk action.")
            count += 1
        self.message_user(request, f"Reversed {count} commission(s).")
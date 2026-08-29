from django.contrib import admin

from .models import AffiliateClick, AffiliateLink, AffiliateProfile
from .services import approve_affiliate, reject_affiliate, suspend_affiliate



@admin.register(AffiliateProfile)
class AffiliateProfileAdmin(admin.ModelAdmin):
    list_display = ["affiliate_code", "user", "status", "commission_rate", "created_at"]
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
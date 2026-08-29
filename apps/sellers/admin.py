from django.contrib import admin

from .models import SellerProfile
from .services import approve_seller, reject_seller, suspend_seller


@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    list_display = ["store_name", "user", "status", "commission_rate", "created_at"]
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

from django.contrib import admin

from .models import RiderProfile
from .services import approve_rider, reject_rider, suspend_rider, verify_rider


@admin.register(RiderProfile)
class RiderProfileAdmin(admin.ModelAdmin):
    list_display = [
        "full_name", "user", "status", "vehicle_type",
        "service_area", "verified", "is_available", "created_at",
    ]
    list_filter = ["status", "vehicle_type", "verified", "is_available"]
    search_fields = ["full_name", "user__username", "user__email", "phone", "service_area"]
    readonly_fields = ["reviewed_at", "reviewed_by"]
    actions = ["approve_riders", "reject_riders", "suspend_riders", "verify_riders"]

    @admin.action(description="Approve selected riders")
    def approve_riders(self, request, queryset):
        for profile in queryset:
            approve_rider(profile=profile, reviewed_by=request.user)
        self.message_user(request, f"Approved {queryset.count()} rider(s).")

    @admin.action(description="Reject selected riders")
    def reject_riders(self, request, queryset):
        for profile in queryset:
            reject_rider(profile=profile, reviewed_by=request.user, reason="Rejected via admin bulk action.")
        self.message_user(request, f"Rejected {queryset.count()} rider(s).")

    @admin.action(description="Suspend selected riders")
    def suspend_riders(self, request, queryset):
        for profile in queryset:
            suspend_rider(profile=profile, reviewed_by=request.user, reason="Suspended via admin bulk action.")
        self.message_user(request, f"Suspended {queryset.count()} rider(s).")

    @admin.action(description="Mark selected riders as verified")
    def verify_riders(self, request, queryset):
        for profile in queryset:
            verify_rider(profile=profile, reviewed_by=request.user)
        self.message_user(request, f"Verified {queryset.count()} rider(s).")
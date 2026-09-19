from django.contrib import admin

from apps.core.admin_badges import status_badge

from .models import RiderEarning, RiderProfile
from .services import (
    approve_rider,
    cancel_rider_earning,
    confirm_rider_earning,
    mark_rider_earning_available,
    mark_rider_earning_paid,
    reject_rider,
    reverse_rider_earning,
    suspend_rider,
    verify_rider,
)


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


@admin.register(RiderEarning)
class RiderEarningAdmin(admin.ModelAdmin):
    """
    Spec sections 16/24. Earnings are system-generated (never created/
    edited by hand - see apps.riders.services.record_rider_earning,
    called from apps.logistics.services when a leg is completed), so
    this is read-only except for the status-transition actions below,
    mirroring apps.sellers.admin.SellerEarningAdmin exactly.
    """

    list_display = ["rider", "order", "leg_display", "amount", "status_display", "created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["rider__full_name", "order__reference"]
    readonly_fields = ["rider", "order", "pickup_task", "delivery_task", "amount", "reversal_of", "confirmed_at"]
    actions = ["confirm_earnings", "mark_available", "mark_paid", "cancel_earnings", "reverse_earnings"]

    def has_add_permission(self, request):
        return False

    @admin.display(description="Leg")
    def leg_display(self, obj):
        return obj.leg.title()

    @admin.display(description="Status", ordering="status")
    def status_display(self, obj):
        return status_badge(obj.get_status_display(), obj.status)

    @admin.action(description="Confirm selected earnings (pending -> held)")
    def confirm_earnings(self, request, queryset):
        count = 0
        for earning in queryset.filter(status="pending"):
            confirm_rider_earning(earning=earning)
            count += 1
        self.message_user(request, f"Confirmed {count} earning(s).")

    @admin.action(description="Mark selected earnings available for payout")
    def mark_available(self, request, queryset):
        count = 0
        for earning in queryset.filter(status="confirmed"):
            mark_rider_earning_available(earning=earning)
            count += 1
        self.message_user(request, f"Marked {count} earning(s) available.")

    @admin.action(description="Mark selected earnings as paid (withdrawn)")
    def mark_paid(self, request, queryset):
        count = 0
        for earning in queryset.filter(status="available"):
            mark_rider_earning_paid(earning=earning)
            count += 1
        self.message_user(request, f"Marked {count} earning(s) paid.")

    @admin.action(description="Cancel selected earnings")
    def cancel_earnings(self, request, queryset):
        count = 0
        for earning in queryset.exclude(status__in=["paid", "reversed"]):
            cancel_rider_earning(earning=earning, reason="Cancelled via admin bulk action.")
            count += 1
        self.message_user(request, f"Cancelled {count} earning(s).")

    @admin.action(description="Reverse selected earnings (e.g. after a refund)")
    def reverse_earnings(self, request, queryset):
        count = 0
        for earning in queryset.exclude(status__in=["cancelled", "reversed"]):
            reverse_rider_earning(earning=earning, reason="Reversed via admin bulk action.")
            count += 1
        self.message_user(request, f"Reversed {count} earning(s).")
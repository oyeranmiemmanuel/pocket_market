from django.contrib import admin

from apps.core.admin_badges import status_badge
from apps.core.fields import mask_value

from .models import AffiliateKYC, BuyerKYC, KYCAuditLog, RiderKYC, SellerKYC
from .services import confirm_kyc, move_under_review, reject_kyc


class BaseKYCAdmin(admin.ModelAdmin):
    """
    Shared admin behaviour for all four KYC models. Sensitive fields
    never appear in list_display/search_fields (spec: "no unnecessary
    exposure") - only masked_* helpers do. Review only ever happens
    through these actions -> apps.kyc.services, never a direct status
    edit, and is gated by Django's own staff/permission system, same as
    apps.sellers/riders/affiliates admin review.
    """

    list_filter = ["status"]
    actions = ["move_under_review_action", "confirm_action", "reject_action"]

    def has_add_permission(self, request):
        return False  # only ever created via the user-facing submit flow

    @admin.display(description="Status")
    def status_display(self, obj):
        return status_badge(obj.get_status_display(), obj.status)

    @admin.action(description="Move selected records under review")
    def move_under_review_action(self, request, queryset):
        count = 0
        for instance in queryset.filter(status="submitted"):
            move_under_review(instance=instance, actor=request.user)
            count += 1
        self.message_user(request, f"Moved {count} record(s) under review.")

    @admin.action(description="Confirm selected KYC records")
    def confirm_action(self, request, queryset):
        count = 0
        for instance in queryset.filter(status__in=["submitted", "under_review"]):
            confirm_kyc(instance=instance, reviewed_by=request.user)
            count += 1
        self.message_user(request, f"Confirmed {count} record(s).")

    @admin.action(description="Reject selected records (resubmission allowed)")
    def reject_action(self, request, queryset):
        count = 0
        for instance in queryset.filter(status__in=["submitted", "under_review"]):
            reject_kyc(instance=instance, reviewed_by=request.user, reason="Rejected via admin bulk action.")
            count += 1
        self.message_user(request, f"Rejected {count} record(s), resubmission allowed.")


@admin.register(BuyerKYC)
class BuyerKYCAdmin(BaseKYCAdmin):
    list_display = ["user", "full_name", "status_display", "city", "submitted_at"]
    search_fields = ["user__username", "user__email", "full_name"]
    readonly_fields = ["submitted_at", "reviewed_at", "reviewed_by"]


@admin.register(SellerKYC)
class SellerKYCAdmin(BaseKYCAdmin):
    list_display = ["seller", "business_type", "status_display", "masked_id_number", "submitted_at"]
    search_fields = ["seller__store_name", "contact_email"]
    readonly_fields = ["submitted_at", "reviewed_at", "reviewed_by"]

    @admin.display(description="ID Number")
    def masked_id_number(self, obj):
        return mask_value(obj.id_document_number)


@admin.register(AffiliateKYC)
class AffiliateKYCAdmin(BaseKYCAdmin):
    list_display = ["affiliate", "display_name", "status_display", "masked_id_number", "submitted_at"]
    search_fields = ["affiliate__affiliate_code", "contact_email"]
    readonly_fields = ["submitted_at", "reviewed_at", "reviewed_by"]

    @admin.display(description="ID Number")
    def masked_id_number(self, obj):
        return mask_value(obj.id_document_number)


@admin.register(RiderKYC)
class RiderKYCAdmin(BaseKYCAdmin):
    list_display = ["rider", "status_display", "masked_license", "plate_number", "submitted_at"]
    search_fields = ["rider__full_name", "plate_number"]
    readonly_fields = ["submitted_at", "reviewed_at", "reviewed_by"]

    @admin.display(description="Licence No.")
    def masked_license(self, obj):
        return mask_value(obj.drivers_license_number)


@admin.register(KYCAuditLog)
class KYCAuditLogAdmin(admin.ModelAdmin):
    """Read-only - rows are only ever created by apps.kyc.services."""

    list_display = ["created_at", "content_type", "object_id", "actor", "action", "from_status", "to_status"]
    list_filter = ["action", "content_type"]
    readonly_fields = [f.name for f in KYCAuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
from django.contrib import admin

from apps.core.admin_badges import status_badge

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """
    Read-only in admin - notifications are a log of what a user was told
    and when, not something staff edit. Mainly useful for support/
    debugging ("did this seller actually get notified their payout
    failed?") rather than day-to-day management.
    """

    list_display = ["user", "category", "message", "read_status", "created_at"]
    list_filter = ["category", "is_read", "created_at"]
    search_fields = ["user__username", "user__email", "message"]
    list_per_page = 50
    date_hierarchy = "created_at"

    @admin.display(description="Status", ordering="is_read")
    def read_status(self, obj):
        return status_badge("Read" if obj.is_read else "Unread", "delivered" if obj.is_read else "pending")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

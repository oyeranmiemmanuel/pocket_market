from django.contrib import admin
from django.urls import path

from .admin_views import platform_analytics_view
from .models import LedgerEntry


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    """
    Pure audit trail - never created or edited by hand (see
    apps.ledger.services.process_order_financials /
    reverse_order_item_financials), so entirely read-only in admin.
    """

    list_display = [
        "reference", "entry_type", "order_item", "gross_amount",
        "platform_commission_amount", "seller_earning_amount",
        "affiliate_commission_amount", "net_payable_amount", "created_at",
    ]
    list_filter = ["entry_type", "currency", "created_at"]
    search_fields = ["reference", "order__reference"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

# Phase 12 - bolts a custom page onto the existing Django admin (spec
# section 32: "extend the existing Django admin") rather than a
# separate app/URL namespace. Standard Django pattern: wrap
# admin.site.get_urls so our route is registered alongside the built-in
# ones, protected the same way (admin.site.admin_view enforces staff
# login exactly like every other admin page).
_original_get_urls = admin.site.get_urls


def _get_urls_with_analytics():
    custom_urls = [
        path("analytics/", admin.site.admin_view(platform_analytics_view), name="platform_analytics"),
    ]
    return custom_urls + _original_get_urls()


admin.site.get_urls = _get_urls_with_analytics

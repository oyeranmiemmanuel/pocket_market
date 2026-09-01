from django.contrib import admin

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
from django.contrib import admin

from apps.core.admin_badges import status_badge

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["reference", "order", "status_display", "provider", "amount", "paid_at"]
    list_filter = ["status", "provider"]
    search_fields = ["reference", "provider_reference", "order__reference"]
    readonly_fields = ["reference", "amount", "paid_at"]
    list_per_page = 25
    date_hierarchy = "paid_at"

    @admin.display(description="Status", ordering="status")
    def status_display(self, obj):
        return status_badge(obj.get_status_display(), obj.status)

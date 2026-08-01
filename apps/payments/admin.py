from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["reference", "order", "status", "amount", "paid_at"]
    list_filter = ["status", "provider"]
    search_fields = ["reference", "provider_reference", "order__reference"]

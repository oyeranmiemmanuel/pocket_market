from django.contrib import admin, messages

from apps.core.admin_badges import status_badge
from apps.core.exceptions import ValidationFailedError

from .models import Order, OrderItem, Refund, RefundEvidence, ShippingAddress
from .services import approve_refund, begin_refund_processing, reject_refund, start_return, start_review


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["product", "product_name", "unit_price", "quantity", "seller", "fulfillment_status"]


class ShippingAddressInline(admin.StackedInline):
    model = ShippingAddress
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["reference", "full_name", "email", "status_display", "total", "created_at"]
    list_filter = ["status", "delivery_method", "created_at"]
    search_fields = ["reference", "email", "full_name"]
    readonly_fields = ["reference", "subtotal", "shipping_fee", "total", "created_at", "updated_at"]
    inlines = [OrderItemInline, ShippingAddressInline]
    list_per_page = 25
    date_hierarchy = "created_at"

    fieldsets = (
        ("Order", {
            "fields": ("reference", "user", "status", "delivery_method"),
        }),
        ("Customer", {
            "fields": ("full_name", "email", "phone"),
        }),
        ("Amounts", {
            "fields": ("subtotal", "shipping_fee", "total"),
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description="Status", ordering="status")
    def status_display(self, obj):
        return status_badge(obj.get_status_display(), obj.status)


class RefundEvidenceInline(admin.TabularInline):
    model = RefundEvidence
    extra = 0
    readonly_fields = ["file", "uploaded_by", "created_at"]


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    """
    The "platform" side of spec sections 26-27. Seller actions
    (confirm receipt, confirm condition) live in the seller-facing
    views instead - this admin only exposes the platform-only steps:
    review, deciding a return is needed, final approval, and (after the
    mandatory delay has genuinely elapsed) starting processing.
    """

    list_display = ["order_item", "reason_category", "amount", "status_display", "created_at"]
    list_filter = ["status", "reason_category"]
    search_fields = ["order_item__product_name", "order_item__order__reference"]
    readonly_fields = [
        "order_item", "requested_by", "amount", "item_received_at", "seller_condition_notes",
        "seller_condition_confirmed_at", "approved_at", "provider_reference", "processed_at",
    ]
    inlines = [RefundEvidenceInline]
    actions = ["start_review_action", "start_return_action", "approve_action", "reject_action", "begin_processing_action"]
    list_per_page = 25

    @admin.display(description="Status", ordering="status")
    def status_display(self, obj):
        return status_badge(obj.get_status_display(), obj.status)

    def _run(self, request, queryset, fn, success_msg):
        done = 0
        for refund in queryset:
            try:
                fn(refund)
            except ValidationFailedError as e:
                self.message_user(request, f"{refund}: {e}", level=messages.ERROR)
            else:
                done += 1
        if done:
            self.message_user(request, f"{success_msg} ({done})", level=messages.SUCCESS)

    @admin.action(description="Move to Under Review")
    def start_review_action(self, request, queryset):
        self._run(request, queryset, lambda r: start_review(refund=r, reviewed_by=request.user), "Moved to review")

    @admin.action(description="Start Return (physical items only)")
    def start_return_action(self, request, queryset):
        self._run(request, queryset, lambda r: start_return(refund=r), "Return started")

    @admin.action(description="Approve (starts the mandatory delay)")
    def approve_action(self, request, queryset):
        self._run(request, queryset, lambda r: approve_refund(refund=r, reviewed_by=request.user), "Approved")

    @admin.action(description="Reject")
    def reject_action(self, request, queryset):
        self._run(request, queryset, lambda r: reject_refund(refund=r, reviewed_by=request.user), "Rejected")

    @admin.action(description="Begin Processing (fails if delay hasn't elapsed)")
    def begin_processing_action(self, request, queryset):
        self._run(request, queryset, lambda r: begin_refund_processing(refund=r), "Processing started")

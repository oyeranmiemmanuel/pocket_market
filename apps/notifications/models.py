"""
Section 11 of the frontend roadmap - "Start with Django messages and/or
simple notification UI... Real-time notifications are LATER."

Django's `messages` framework only works within the request/response cycle
of the user who triggers it - it can't tell a *different* user about
something later (a seller shipping an item doesn't happen in the
customer's request; an admin approving a seller application doesn't
happen in the seller's request). Anything crossing between users needs to
be persisted somewhere and read back on that user's next visit - that's
what this model is for. `messages` is still used as-is everywhere the
acting user is also the one who should see the confirmation (e.g. "Cart
updated") - this app is only for the cross-user cases.

Deliberately NOT real-time (no websockets/push/polling) - a notification
is just a row the recipient sees next time they load /notifications/ or
glance at the nav badge count. That matches the roadmap's explicit
scoping for this stage.
"""

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class NotificationCategory(models.TextChoices):
    # Customer-facing
    ORDER_PLACED = "order_placed", "Order Placed"
    PAYMENT_SUCCESSFUL = "payment_successful", "Payment Successful"
    ORDER_PROCESSING = "order_processing", "Order Processing"
    ORDER_SHIPPED = "order_shipped", "Order Shipped"
    ORDER_DELIVERED = "order_delivered", "Order Delivered"
    # Seller-facing
    SELLER_APPLICATION_APPROVED = "seller_application_approved", "Seller Application Approved"
    SELLER_APPLICATION_REJECTED = "seller_application_rejected", "Seller Application Rejected"
    SELLER_NEW_ORDER = "seller_new_order", "New Order"
    SELLER_PAYOUT_STATUS = "seller_payout_status", "Payout Status"
    # Affiliate-facing
    AFFILIATE_NEW_CONVERSION = "affiliate_new_conversion", "New Conversion"
    AFFILIATE_COMMISSION_CONFIRMED = "affiliate_commission_confirmed", "Commission Confirmed"
    AFFILIATE_COMMISSION_CANCELLED = "affiliate_commission_cancelled", "Commission Cancelled"
    AFFILIATE_PAYOUT_STATUS = "affiliate_payout_status", "Payout Status"


class Notification(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    category = models.CharField(max_length=40, choices=NotificationCategory.choices)

    message = models.CharField(max_length=255)

    url = models.CharField(
        max_length=255,
        blank=True,
        help_text="Where clicking this notification should take the user, if anywhere.",
    )

    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read", "created_at"]),
        ]

    def __str__(self):
        return f"{self.get_category_display()} for {self.user}: {self.message}"

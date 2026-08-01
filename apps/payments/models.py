from django.db import models

from apps.core.models import BaseModel
from apps.orders.models import Order


class PaymentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"


class Payment(BaseModel):
    """
    One row per payment *attempt* against an Order - not unique on order,
    since a failed attempt can be retried with a fresh reference without
    losing the history of what happened.
    """

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")

    reference = models.CharField(max_length=100, unique=True)

    provider = models.CharField(max_length=20, default="paystack")

    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)

    provider_reference = models.CharField(max_length=100, blank=True)

    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payment {self.reference} ({self.status})"

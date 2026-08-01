from django.db import models

from apps.core.enums import DeliveryMethod, DeliveryStatus
from apps.core.models import BaseModel
from apps.orders.models import Order

# Which DeliveryStatus values are valid for each method, in progression
# order. Local delivery skips the shipping-only stages entirely (see the
# docstring on core.enums.DeliveryStatus for why).
LOCAL_DELIVERY_STAGES = [
    DeliveryStatus.ORDER_CONFIRMED,
    DeliveryStatus.PREPARING,
    DeliveryStatus.OUT_FOR_DELIVERY,
    DeliveryStatus.DELIVERED,
]

SHIPPING_STAGES = [
    DeliveryStatus.ORDER_CONFIRMED,
    DeliveryStatus.PREPARING,
    DeliveryStatus.READY_FOR_SHIPPING,
    DeliveryStatus.SHIPPED,
    DeliveryStatus.IN_TRANSIT,
    DeliveryStatus.OUT_FOR_DELIVERY,
    DeliveryStatus.DELIVERED,
]

# Exception states, valid for either method at any point.
EXCEPTION_STAGES = [DeliveryStatus.FAILED_DELIVERY, DeliveryStatus.CANCELLED]


class Delivery(BaseModel):
    """
    One per Order. Which of LOCAL_DELIVERY_STAGES / SHIPPING_STAGES
    applies depends on `method`. Created automatically once payment
    succeeds (apps.payments.services._finalize_successful_payment).
    """

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="delivery")

    method = models.CharField(max_length=20, choices=DeliveryMethod.choices)

    current_stage = models.CharField(max_length=30, choices=DeliveryStatus.choices)

    estimated_delivery_date = models.DateField(null=True, blank=True)

    # Shipping-specific (carrier tracking number). Blank for local delivery.
    tracking_number = models.CharField(max_length=100, blank=True)
    carrier_name = models.CharField(max_length=100, blank=True)

    # Local-delivery-specific (who's bringing it). Blank for shipping.
    courier_name = models.CharField(max_length=100, blank=True)
    courier_phone = models.CharField(max_length=20, blank=True)

    class Meta:
        verbose_name_plural = "Deliveries"

    def __str__(self):
        return f"Delivery for {self.order.reference} ({self.get_current_stage_display()})"

    @property
    def stages_in_order(self):
        """The right stage progression for this delivery's method."""
        method_stages = (
            LOCAL_DELIVERY_STAGES if self.method == DeliveryMethod.LOCAL_DELIVERY else SHIPPING_STAGES
        )
        return [s.value for s in method_stages]

    @property
    def is_delivered(self):
        return self.current_stage == DeliveryStatus.DELIVERED

    @property
    def is_exception(self):
        return self.current_stage in (DeliveryStatus.FAILED_DELIVERY, DeliveryStatus.CANCELLED)

    @property
    def progress_percent(self):
        """For a progress bar - how far through this method's pipeline."""
        stages = self.stages_in_order
        if self.current_stage not in stages:
            return 0
        return int((stages.index(self.current_stage) + 1) / len(stages) * 100)


class DeliveryUpdate(BaseModel):
    """
    Timestamped tracking history - one row per stage change (or ad-hoc
    note), so the customer sees an accurate timeline, not just a single
    current status.
    """

    delivery = models.ForeignKey(Delivery, on_delete=models.CASCADE, related_name="updates")

    stage = models.CharField(max_length=30, choices=DeliveryStatus.choices)

    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.delivery.order.reference} -> {self.stage}"

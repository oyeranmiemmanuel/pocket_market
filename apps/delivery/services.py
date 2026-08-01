"""
Delivery lifecycle - creating a Delivery once an order is paid, and
advancing it through its method-specific stages.
"""

import datetime

from django.utils import timezone

from apps.core.enums import DeliveryMethod, DeliveryStatus
from apps.core.exceptions import ValidationFailedError
from apps.orders.models import Order, OrderStatus

from .models import EXCEPTION_STAGES, Delivery, DeliveryUpdate

# Rough estimates, not tied to a real carrier/routing API yet - local
# delivery is deliberately much shorter so the ETA itself communicates
# "this is the fast option", not just the status wording.
LOCAL_DELIVERY_ETA_DAYS = 1
SHIPPING_ETA_DAYS = 5


def create_delivery(order: Order, method: str) -> Delivery:
    """Called once payment succeeds - see apps.payments.services."""

    eta_days = LOCAL_DELIVERY_ETA_DAYS if method == DeliveryMethod.LOCAL_DELIVERY else SHIPPING_ETA_DAYS

    delivery = Delivery.objects.create(
        order=order,
        method=method,
        current_stage=DeliveryStatus.ORDER_CONFIRMED,
        estimated_delivery_date=timezone.now().date() + datetime.timedelta(days=eta_days),
    )

    DeliveryUpdate.objects.create(
        delivery=delivery,
        stage=DeliveryStatus.ORDER_CONFIRMED,
        note="Order confirmed and payment received.",
    )

    return delivery


def advance_stage(delivery: Delivery, new_stage: str, note: str = "") -> Delivery:
    """
    Move a delivery to its next (or any) stage, logging a DeliveryUpdate.
    Validates new_stage actually belongs to this delivery's method - so a
    local delivery can never be pushed into a shipping-only stage
    (READY_FOR_SHIPPING/SHIPPED/IN_TRANSIT) or vice versa. Exception
    stages (failed/cancelled) are always allowed regardless of method.
    """
    valid_stages = delivery.stages_in_order + [s.value for s in EXCEPTION_STAGES]

    if new_stage not in valid_stages:
        raise ValidationFailedError(
            f"'{new_stage}' is not a valid stage for {delivery.get_method_display()}."
        )

    delivery.current_stage = new_stage
    delivery.save(update_fields=["current_stage"])

    DeliveryUpdate.objects.create(delivery=delivery, stage=new_stage, note=note)

    if new_stage == DeliveryStatus.DELIVERED:
        order = delivery.order
        order.status = OrderStatus.DELIVERED
        order.save(update_fields=["status"])

    return delivery

"""
Delivery lifecycle - creating a Delivery once an order is paid, and
advancing it through its method-specific stages.
"""

import datetime

from django.urls import reverse
from django.utils import timezone

from apps.core.enums import DeliveryMethod, DeliveryStatus
from apps.core.exceptions import ValidationFailedError
from apps.notifications.models import NotificationCategory
from apps.notifications.services import create_notification
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

    order = delivery.order
    order_url = reverse("orders:order_detail", args=[order.reference])

    # Maps delivery stages onto the three customer-facing lifecycle
    # notifications the roadmap asks for (processing/shipped/delivered).
    # SHIPPED and OUT_FOR_DELIVERY both count as "shipped" here because
    # local delivery deliberately skips the SHIPPED stage entirely and
    # goes straight to OUT_FOR_DELIVERY (see DeliveryStatus's docstring) -
    # without this, a local-delivery customer would never get a
    # "shipped" notification at all.
    if new_stage == DeliveryStatus.PREPARING:
        create_notification(
            user=order.user,
            category=NotificationCategory.ORDER_PROCESSING,
            message=f"Your order {order.reference} is being processed.",
            url=order_url,
        )
    elif new_stage in (DeliveryStatus.SHIPPED, DeliveryStatus.OUT_FOR_DELIVERY):
        create_notification(
            user=order.user,
            category=NotificationCategory.ORDER_SHIPPED,
            message=f"Your order {order.reference} is on its way.",
            url=order_url,
        )
    elif new_stage == DeliveryStatus.DELIVERED:
        order.status = OrderStatus.DELIVERED
        order.save(update_fields=["status"])
        create_notification(
            user=order.user,
            category=NotificationCategory.ORDER_DELIVERED,
            message=f"Your order {order.reference} has been delivered.",
            url=order_url,
        )

    return delivery

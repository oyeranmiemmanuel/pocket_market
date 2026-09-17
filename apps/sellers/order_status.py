"""
Seller order-management page support (spec section 8).

The page needs to show one combined status per line item - Pending,
Confirmed, Preparing, Ready for Pickup, Assigned to Rider, Picked Up, In
Transit, Delivered, Refund Requested, Completed - but no single model
in this codebase owns that whole lifecycle. Each piece already lives
somewhere and already works:

    OrderItem.fulfillment_status   seller's own pending/processing/... update
    apps.logistics.SellerFulfillment.status   this seller's pickup readiness
    apps.logistics.PickupTask.status/.rider   who's collecting it, and from whom
    apps.delivery.Delivery.current_stage      the customer-facing tracking stage
    apps.orders.Refund.status                 any refund request on the item
    apps.sellers.SellerEarning.status         whether the money has cleared

Rather than duplicating all of that into a new stored field that could
drift out of sync with the systems that actually drive it,
SellerOrderStatus is derived at read time from whatever combination of
those already exists for a given item. Nothing here writes to any
model - it's display/filtering only.
"""
from django.db import models

from apps.core.enums import DeliveryStatus, FulfillmentStatus, RefundStatus
from apps.logistics.models import PickupTaskStatus, SellerFulfillment, SellerFulfillmentStatus
from apps.orders.models import OrderItem

from .models import EarningStatus

_ACTIVE_REFUND_STATUSES = (RefundStatus.REQUESTED, RefundStatus.PROCESSING)
_SETTLED_EARNING_STATUSES = (EarningStatus.AVAILABLE, EarningStatus.PAID)
_ASSIGNED_PICKUP_STATUSES = (PickupTaskStatus.ASSIGNED, PickupTaskStatus.EN_ROUTE)
_IN_TRANSIT_DELIVERY_STAGES = (DeliveryStatus.IN_TRANSIT, DeliveryStatus.OUT_FOR_DELIVERY)


class SellerOrderStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    CONFIRMED = "confirmed", "Confirmed"
    PREPARING = "preparing", "Preparing"
    READY_FOR_PICKUP = "ready_for_pickup", "Ready for Pickup"
    ASSIGNED_TO_RIDER = "assigned_to_rider", "Assigned to Rider"
    PICKED_UP = "picked_up", "Picked Up"
    IN_TRANSIT = "in_transit", "In Transit"
    DELIVERED = "delivered", "Delivered"
    REFUND_REQUESTED = "refund_requested", "Refund Requested"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"  # not in the spec's filter list, kept for completeness


def seller_order_item_queryset(seller_profile):
    """
    Every OrderItem belonging to this seller, prefetched so
    build_seller_order_row() below runs no further queries per row.
    """
    return (
        OrderItem.objects.filter(seller=seller_profile)
        .select_related("order", "order__delivery", "order__delivery__delivery_task", "order__shipping_address")
        .prefetch_related(
            "refunds",
            "seller_earnings",
            models.Prefetch(
                "order__seller_fulfillments",
                queryset=SellerFulfillment.objects.filter(seller=seller_profile)
                .prefetch_related("packages__pickup_tasks__rider"),
                to_attr="_prefetched_fulfillments",
            ),
        )
        .order_by("-created_at")
    )


def _current_earning(item):
    # Unique-per-item, non-reversal row (see SellerEarning's constraint);
    # its own .status flips to REVERSED once a refund reverses it, so
    # this one row is always the right thing to show.
    for earning in item.seller_earnings.all():
        if earning.reversal_of_id is None:
            return earning
    return None


def _latest_refund(item):
    refunds = list(item.refunds.all())  # Refund.Meta.ordering = ["-created_at"]
    return refunds[0] if refunds else None


def _seller_fulfillment(item):
    for fulfillment in getattr(item.order, "_prefetched_fulfillments", []):
        if fulfillment.seller_id == item.seller_id:
            return fulfillment
    return None


def _pickup_task_and_rider(fulfillment):
    if fulfillment is None:
        return None, None
    for package in fulfillment.packages.all():
        tasks = list(package.pickup_tasks.all())  # PickupTask.Meta.ordering = ["-created_at"]
        if tasks:
            task = tasks[0]
            return task, task.rider
    return None, None


def _delivery_rider(delivery):
    if delivery is None:
        return None
    delivery_task = getattr(delivery, "delivery_task", None)
    return delivery_task.rider if delivery_task is not None else None


def _derive_status(*, item, order, fulfillment, pickup_task, delivery, refund):
    if refund is not None and refund.status in _ACTIVE_REFUND_STATUSES:
        return SellerOrderStatus.REFUND_REQUESTED

    if item.fulfillment_status == FulfillmentStatus.CANCELLED:
        return SellerOrderStatus.CANCELLED

    if not order.is_paid:
        return SellerOrderStatus.PENDING

    if item.fulfillment_status == FulfillmentStatus.DELIVERED:
        earning = _current_earning(item)
        if earning is not None and earning.status in _SETTLED_EARNING_STATUSES:
            return SellerOrderStatus.COMPLETED
        return SellerOrderStatus.DELIVERED

    if delivery is not None and delivery.current_stage in _IN_TRANSIT_DELIVERY_STAGES:
        return SellerOrderStatus.IN_TRANSIT

    if fulfillment is not None and fulfillment.status == SellerFulfillmentStatus.PICKED_UP:
        return SellerOrderStatus.PICKED_UP

    if pickup_task is not None and pickup_task.status in _ASSIGNED_PICKUP_STATUSES:
        return SellerOrderStatus.ASSIGNED_TO_RIDER

    if fulfillment is not None and fulfillment.status == SellerFulfillmentStatus.READY_FOR_PICKUP:
        return SellerOrderStatus.READY_FOR_PICKUP

    if item.fulfillment_status == FulfillmentStatus.PROCESSING:
        return SellerOrderStatus.PREPARING

    return SellerOrderStatus.CONFIRMED


def _customer_info(order):
    """
    Deliberately conservative: name and delivery area always (needed to
    fulfil the order), phone only when it's a local delivery the seller
    or their rider may need to coordinate directly, email never (no
    fulfilment need, and the surest source of off-platform spam).
    """
    address = getattr(order, "shipping_address", None)
    return {
        "full_name": order.full_name,
        "area": f"{address.city}, {address.state}" if address else "",
        "phone": order.phone if order.delivery_method == "local_delivery" else "",
    }


def build_seller_order_row(item):
    order = item.order
    delivery = getattr(order, "delivery", None)
    fulfillment = _seller_fulfillment(item)
    pickup_task, pickup_rider = _pickup_task_and_rider(fulfillment)
    refund = _latest_refund(item)
    earning = _current_earning(item)
    rider = pickup_rider or _delivery_rider(delivery)

    status = _derive_status(
        item=item, order=order, fulfillment=fulfillment,
        pickup_task=pickup_task, delivery=delivery, refund=refund,
    )

    return {
        "item": item,
        "order": order,
        "customer": _customer_info(order),
        "status": status.value,
        "status_label": status.label,
        "delivery": delivery,
        "rider": rider,
        "refund": refund,
        "earning": earning,
    }

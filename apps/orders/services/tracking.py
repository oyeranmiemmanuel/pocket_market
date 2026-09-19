"""
Buyer-facing order tracking (spec section 20) - per-seller pickup status
grouped with the order's single shared final-delivery leg.

Deliberately does NOT claim independent per-seller "In Transit"/"Delivered"
states: apps.delivery.Delivery (and apps.logistics.DeliveryTask) are one
row per ORDER, not one per seller, so once packages are picked up, the
final delivery leg is genuinely shared across every seller on that order.
Only pickup is truly independent per seller (a different rider can
collect each seller's package) - that's the one place per-seller data
actually exists in this schema. See the section-20 gap analysis for the
bigger schema change that would be needed to make the final leg
independent too, if that's ever wanted.
"""
from decimal import Decimal

from apps.core.constants import LOCAL_DELIVERY_FEE, SHIPPING_FEE
from apps.core.enums import DeliveryMethod
from apps.logistics.models import SellerFulfillment, SellerFulfillmentStatus


def _delivery_fee_for(method):
    return Decimal(LOCAL_DELIVERY_FEE) if method == DeliveryMethod.LOCAL_DELIVERY else Decimal(SHIPPING_FEE)


def build_order_tracking(order):
    """
    One row per seller on this order: Confirmed/Picked Up (independent,
    real per-seller state), that seller's own delivery fee, and whichever
    rider collected their package. Computed fresh each call rather than
    stored - SellerFulfillment/PickupTask already ARE the persisted
    state, this just reshapes it for the template.
    """
    fulfillments = {
        f.seller_id: f
        for f in SellerFulfillment.objects.filter(order=order).prefetch_related("packages__pickup_tasks__rider")
    }

    groups = {}
    for item in order.items.select_related("seller"):
        seller = item.seller
        key = seller.id if seller else None
        group = groups.setdefault(key, {
            "seller_name": seller.store_name if seller else "Top Tech",
            "items": [],
        })
        group["items"].append(item)

    fee = _delivery_fee_for(order.delivery_method)
    rows = []
    for key, group in groups.items():
        fulfillment = fulfillments.get(key)
        picked_up = fulfillment is not None and fulfillment.status == SellerFulfillmentStatus.PICKED_UP

        rider = None
        if fulfillment is not None:
            for package in fulfillment.packages.all():
                tasks = list(package.pickup_tasks.all())  # PickupTask.Meta.ordering = ["-created_at"]
                if tasks and tasks[0].rider_id:
                    rider = tasks[0].rider
                    break

        rows.append({
            "seller_name": group["seller_name"],
            "items": group["items"],
            "confirmed": order.is_paid,
            "picked_up": picked_up,
            "rider": rider,
            "delivery_fee": fee,
        })

    rows.sort(key=lambda r: r["seller_name"].lower())
    return rows

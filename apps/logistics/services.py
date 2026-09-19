"""
Phase 2 - logistics boundary services.

Deliberately minimal: this gives a seller a way to mark their slice of
an order ready, gives a rider a way to see/accept an individual pickup
or delivery task, and gives staff/ops a way to group tasks into a
CollectionBatch by hand. It does NOT implement automatic batch creation,
route optimisation, or dispatch matching - those stay explicit non-goals
of this phase (see apps.logistics.models module docstring). Nothing
here reads apps.kyc data.
"""

from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import ValidationFailedError
from apps.orders.models import Order
from apps.riders.models import RiderProfile

from .models import (
    CollectionBatch,
    CollectionBatchStatus,
    DeliveryTask,
    DeliveryTaskStatus,
    Package,
    PackageItem,
    PackageStatus,
    PickupTask,
    PickupTaskStatus,
    RiderAssignment,
    RiderAssignmentStatus,
    SellerFulfillment,
    SellerFulfillmentStatus,
)


# ---------------------------------------------------------------------------
# Order -> SellerFulfillment
# ---------------------------------------------------------------------------

def create_seller_fulfillments(order: Order):
    """
    Called once payment succeeds (see apps.payments.services.
    _finalize_successful_payment), right alongside
    apps.delivery.services.create_delivery. Creates one SellerFulfillment
    per distinct seller represented in the order's line items.
    Platform-owned items (seller is null) never get one - there's no
    seller to collect a package from.

    Idempotent - safe to call more than once for the same order.
    """
    seller_ids = (
        order.items.exclude(seller__isnull=True).values_list("seller_id", flat=True).distinct()
    )
    fulfillments = []
    for seller_id in seller_ids:
        fulfillment, _ = SellerFulfillment.objects.get_or_create(order=order, seller_id=seller_id)
        fulfillments.append(fulfillment)
    return fulfillments


# ---------------------------------------------------------------------------
# SellerFulfillment -> Package -> PickupTask
# ---------------------------------------------------------------------------

@transaction.atomic
def mark_fulfillment_ready(fulfillment: SellerFulfillment) -> Package:
    """
    A seller confirming "this is ready for a rider to collect" - the one
    piece of the future consolidated-pickup flow this phase wires up
    end-to-end. Creates a single Package covering every OrderItem in
    this fulfillment (splitting into multiple packages is supported by
    the schema - see Package/PackageItem - but not exposed in the UI
    yet) and one PickupTask for it.

    Calling this again once already ready is a safe no-op that returns
    the existing package.
    """
    if fulfillment.status == SellerFulfillmentStatus.READY_FOR_PICKUP:
        existing = fulfillment.packages.order_by("-created_at").first()
        if existing:
            return existing

    if fulfillment.status != SellerFulfillmentStatus.PENDING:
        raise ValidationFailedError(
            f"Can't mark a {fulfillment.get_status_display()} fulfillment ready."
        )

    order_items = list(fulfillment.order_items)
    if not order_items:
        raise ValidationFailedError("This fulfillment has no order items to package.")

    package = Package.objects.create(fulfillment=fulfillment, status=PackageStatus.READY)

    for item in order_items:
        PackageItem.objects.create(package=package, order_item=item, quantity=item.quantity)

    PickupTask.objects.create(package=package)

    fulfillment.status = SellerFulfillmentStatus.READY_FOR_PICKUP
    fulfillment.ready_at = timezone.now()
    fulfillment.save(update_fields=["status", "ready_at"])

    return package


# ---------------------------------------------------------------------------
# Rider assignment (generic - PickupTask, CollectionBatch, DeliveryTask)
# ---------------------------------------------------------------------------

def _offer_assignment(rider: RiderProfile, target, status=RiderAssignmentStatus.OFFERED) -> RiderAssignment:
    return RiderAssignment.objects.create(rider=rider, assigned_to=target, status=status)


@transaction.atomic
def assign_rider_to_pickup_task(pickup_task: PickupTask, rider: RiderProfile) -> RiderAssignment:
    """
    Simple first-come-first-served acceptance - no matching by service
    area or vehicle type yet. That's future dispatch work; this just
    proves the PickupTask <-> RiderAssignment boundary works.
    """
    if pickup_task.status != PickupTaskStatus.PENDING:
        raise ValidationFailedError("This pickup task is no longer available.")

    pickup_task.rider = rider
    pickup_task.status = PickupTaskStatus.ASSIGNED
    pickup_task.save(update_fields=["rider", "status"])

    return _offer_assignment(rider, pickup_task, status=RiderAssignmentStatus.ACCEPTED)


@transaction.atomic
def mark_package_collected(pickup_task: PickupTask) -> PickupTask:
    if pickup_task.rider is None:
        raise ValidationFailedError("This pickup task hasn't been assigned to a rider yet.")

    pickup_task.status = PickupTaskStatus.COLLECTED
    pickup_task.collected_at = timezone.now()
    pickup_task.save(update_fields=["status", "collected_at"])

    package = pickup_task.package
    package.status = PackageStatus.COLLECTED
    package.save(update_fields=["status"])

    fulfillment = package.fulfillment
    fulfillment.status = SellerFulfillmentStatus.PICKED_UP
    fulfillment.save(update_fields=["status"])

    _credit_rider_for_pickup(pickup_task)

    return pickup_task


def _credit_rider_for_pickup(pickup_task):
    """Spec sections 16/24 - the rider earns a share of this seller's delivery fee for collecting their package."""
    from apps.core.constants import RIDER_PICKUP_EARNING_SHARE
    from apps.orders.services.checkout import delivery_fee_for
    from apps.riders.services import record_rider_earning

    order = pickup_task.package.fulfillment.order
    amount = delivery_fee_for(order.delivery_method) * RIDER_PICKUP_EARNING_SHARE
    record_rider_earning(rider=pickup_task.rider, order=order, amount=amount, pickup_task=pickup_task)


def report_pickup_exception(pickup_task: PickupTask, *, missing: bool, reason: str) -> PickupTask:
    """
    Covers "Missing/not-ready package exceptions" from the spec's
    future-support list at the level this phase actually needs: a rider
    can flag a task rather than silently doing nothing with it.
    """
    pickup_task.status = PickupTaskStatus.MISSING if missing else PickupTaskStatus.NOT_READY
    pickup_task.exception_reason = reason
    pickup_task.save(update_fields=["status", "exception_reason"])
    return pickup_task


# ---------------------------------------------------------------------------
# Delivery -> DeliveryTask (rider's side of the existing customer-facing
# apps.delivery.Delivery)
# ---------------------------------------------------------------------------

def create_delivery_task_for_local_delivery(delivery):
    """
    Called from apps.delivery.services.create_delivery. Only
    local-delivery orders get a rider-facing DeliveryTask - shipping
    orders go to a carrier, not a rider. Idempotent.
    """
    from apps.core.enums import DeliveryMethod

    if delivery.method != DeliveryMethod.LOCAL_DELIVERY:
        return None

    task, _ = DeliveryTask.objects.get_or_create(delivery=delivery)
    return task


@transaction.atomic
def assign_rider_to_delivery_task(delivery_task: DeliveryTask, rider: RiderProfile) -> RiderAssignment:
    delivery_task.rider = rider
    delivery_task.status = DeliveryTaskStatus.ASSIGNED
    delivery_task.save(update_fields=["rider", "status"])

    return _offer_assignment(rider, delivery_task, status=RiderAssignmentStatus.ACCEPTED)


@transaction.atomic
def mark_delivery_task_delivered(delivery_task: DeliveryTask) -> DeliveryTask:
    delivery_task.status = DeliveryTaskStatus.DELIVERED
    delivery_task.delivered_at = timezone.now()
    delivery_task.save(update_fields=["status", "delivered_at"])

    _credit_rider_for_delivery(delivery_task)

    return delivery_task


def _credit_rider_for_delivery(delivery_task):
    """
    Spec sections 16/24. Delivery is one leg per ORDER, not per seller
    (see apps.orders.services.tracking's module docstring), so this
    rider is credited the delivery share of EVERY seller's fee on this
    order, not just one - they're doing the final-mile trip for all of
    them in this one leg.
    """
    if delivery_task.rider is None:
        return

    from apps.core.constants import RIDER_DELIVERY_EARNING_SHARE
    from apps.orders.services.checkout import delivery_fee_for
    from apps.riders.services import record_rider_earning

    order = delivery_task.delivery.order
    distinct_sellers = order.items.exclude(seller__isnull=True).values("seller_id").distinct().count() or 1
    amount = delivery_fee_for(order.delivery_method) * RIDER_DELIVERY_EARNING_SHARE * distinct_sellers
    record_rider_earning(rider=delivery_task.rider, order=order, amount=amount, delivery_task=delivery_task)


# ---------------------------------------------------------------------------
# CollectionBatch - manual/staff-driven only, on purpose. No auto-grouping
# algorithm yet (see apps.logistics.models module docstring).
# ---------------------------------------------------------------------------

def create_batch(notes: str = "") -> CollectionBatch:
    return CollectionBatch.objects.create(notes=notes)


def add_pickup_task_to_batch(batch: CollectionBatch, pickup_task: PickupTask) -> PickupTask:
    pickup_task.batch = batch
    pickup_task.save(update_fields=["batch"])
    return pickup_task


@transaction.atomic
def assign_batch_to_rider(batch: CollectionBatch, rider: RiderProfile) -> CollectionBatch:
    batch.rider = rider
    batch.status = CollectionBatchStatus.ASSIGNED
    batch.assigned_at = timezone.now()
    batch.save(update_fields=["rider", "status", "assigned_at"])

    for task in batch.pickup_tasks.filter(status=PickupTaskStatus.PENDING):
        task.rider = rider
        task.status = PickupTaskStatus.ASSIGNED
        task.save(update_fields=["rider", "status"])

    _offer_assignment(rider, batch, status=RiderAssignmentStatus.ACCEPTED)
    return batch
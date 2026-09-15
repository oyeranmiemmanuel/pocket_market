"""
Phase 2 - logistics / pickup-orchestration boundary layer.
(see MARKETPLACE_BACKEND_IMPLEMENTATION.md, "FUTURE CONSOLIDATED
COLLECTION / PICKUP ORCHESTRATION").

This phase deliberately does NOT implement automatic batching, route
optimisation, or rider-dispatch matching. It only builds the model/API
boundaries so a future "one rider collects from sellers A + B + C in one
run" feature can be added later without rewriting Order, OrderItem,
Delivery, or any existing seller/rider code.

The spec is explicit that the system must NOT be modelled on the
assumption `1 Rider = 1 Seller = 1 Package`. That's why this app keeps
each of the following as its own table instead of collapsing them:

    Order (apps.orders, existing)
      -> SellerFulfillment   one seller's slice of one order
        -> Package           what actually gets physically picked up
          -> PickupTask      the job of collecting one package
            -> RiderAssignment   generic "who's doing this task"
    CollectionBatch          groups many PickupTasks into one rider run
    DeliveryTask             the rider's side of apps.delivery.Delivery
    RouteActivity            ordered stops within a batch

Nothing here is read by pricing, ranking, commission, or payout logic.
Only apps.sellers (seller marks a fulfillment ready) and apps.riders
(rider views/accepts tasks) touch this app, and only through
apps.logistics.services - never by importing these models directly from
other apps' views.

Pickup addresses/contact fields on PickupTask are plain, manually-filled
strings, deliberately NOT auto-populated from apps.kyc.SellerKYC - the
KYC phase's own rule is that confirmed KYC data isn't yet wired into
operational/marketplace decisions, and pickup routing is exactly that
kind of decision. That wiring, if ever wanted, is a future phase's
explicit decision to make, not an accidental side effect of this one.
"""

import uuid

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.core.models import BaseModel
from apps.orders.models import Order, OrderItem
from apps.riders.models import RiderProfile
from apps.sellers.models import SellerProfile


class SellerFulfillmentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    READY_FOR_PICKUP = "ready_for_pickup", "Ready for Pickup"
    PICKED_UP = "picked_up", "Picked Up"
    CANCELLED = "cancelled", "Cancelled"


class PackageStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    READY = "ready", "Ready for Pickup"
    COLLECTED = "collected", "Collected"
    IN_TRANSIT = "in_transit", "In Transit"
    DELIVERED = "delivered", "Delivered"
    EXCEPTION = "exception", "Exception"


class PickupTaskStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ASSIGNED = "assigned", "Assigned"
    EN_ROUTE = "en_route", "Rider En Route"
    COLLECTED = "collected", "Collected"
    NOT_READY = "not_ready", "Seller Not Ready"
    MISSING = "missing", "Package Missing"
    CANCELLED = "cancelled", "Cancelled"


class CollectionBatchStatus(models.TextChoices):
    OPEN = "open", "Open"
    ASSIGNED = "assigned", "Assigned to Rider"
    IN_PROGRESS = "in_progress", "In Progress"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class RiderAssignmentStatus(models.TextChoices):
    OFFERED = "offered", "Offered"
    ACCEPTED = "accepted", "Accepted"
    DECLINED = "declined", "Declined"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class DeliveryTaskStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ASSIGNED = "assigned", "Assigned"
    EN_ROUTE = "en_route", "En Route"
    DELIVERED = "delivered", "Delivered"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"


class RouteActivityType(models.TextChoices):
    PICKUP = "pickup", "Pickup"
    DELIVERY = "delivery", "Delivery"


class RouteActivityStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ARRIVED = "arrived", "Arrived"
    COMPLETED = "completed", "Completed"
    SKIPPED = "skipped", "Skipped"


class SellerFulfillment(BaseModel):
    """
    One row per (order, seller) - a seller's slice of a (possibly
    multi-seller) order.

    Deliberately separate from OrderItem.fulfillment_status, which is
    left completely untouched: that field drives the existing
    seller order-management UI (apps.sellers.order_item_list_view) and
    tracks each *line item's* processing/shipped/delivered state for the
    customer-facing order view. This model tracks the *pickup-side*
    readiness of a seller's whole slice of an order - a different
    lifecycle a rider/pickup system cares about, that can evolve
    independently without touching the seller order UI that already
    works.
    """

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="seller_fulfillments")
    seller = models.ForeignKey(SellerProfile, on_delete=models.CASCADE, related_name="fulfillments")

    status = models.CharField(
        max_length=20,
        choices=SellerFulfillmentStatus.choices,
        default=SellerFulfillmentStatus.PENDING,
    )

    ready_at = models.DateTimeField(null=True, blank=True)

    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "seller_fulfillments"
        constraints = [
            models.UniqueConstraint(fields=["order", "seller"], name="unique_order_seller_fulfillment"),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.seller} - Order {self.order.reference} ({self.get_status_display()})"

    @property
    def order_items(self):
        """The OrderItems that belong to this seller within this order."""
        return OrderItem.objects.filter(order=self.order, seller=self.seller)

    @property
    def is_ready(self):
        return self.status == SellerFulfillmentStatus.READY_FOR_PICKUP


def _package_reference():
    return f"PKG-{uuid.uuid4().hex[:10].upper()}"


class Package(BaseModel):
    """
    The physical parcel a rider actually collects. Modelled as a
    ForeignKey to SellerFulfillment (not OneToOne) - normally one
    package per fulfillment, but a seller splitting one fulfillment into
    several physical parcels should never require a schema change.
    """

    fulfillment = models.ForeignKey(SellerFulfillment, on_delete=models.CASCADE, related_name="packages")

    reference = models.CharField(max_length=20, unique=True, default=_package_reference)

    status = models.CharField(max_length=20, choices=PackageStatus.choices, default=PackageStatus.PENDING)

    weight_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    items = models.ManyToManyField(OrderItem, through="PackageItem", related_name="packages")

    class Meta:
        db_table = "logistics_packages"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference} ({self.get_status_display()})"


class PackageItem(BaseModel):
    """
    Through model - which order items (and what quantity of each) are
    physically inside a given package. Lets a package cover only part
    of a fulfillment later, without changing this table's shape.
    """

    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name="package_items")
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name="package_items")
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "logistics_package_items"
        constraints = [
            models.UniqueConstraint(fields=["package", "order_item"], name="unique_package_order_item"),
        ]

    def __str__(self):
        return f"{self.quantity} x {self.order_item.product_name} in {self.package.reference}"


class CollectionBatch(BaseModel):
    """
    Future orchestration layer: groups several PickupTasks (from
    different sellers) into one rider run. Left almost empty by design
    this phase - there is no auto-batching algorithm and no route
    optimisation. Staff/ops can create one manually (see
    apps.logistics.services.create_batch) and attach PickupTasks to it;
    a later phase can add automatic grouping purely by writing to this
    same table, with no schema change.
    """

    status = models.CharField(
        max_length=20, choices=CollectionBatchStatus.choices, default=CollectionBatchStatus.OPEN,
    )

    rider = models.ForeignKey(
        RiderProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="collection_batches",
    )

    assigned_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "logistics_collection_batches"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Batch {str(self.id)[:8]} ({self.get_status_display()})"


class PickupTask(BaseModel):
    """
    The job of collecting one Package from one seller. Exists
    independently of CollectionBatch so a single pickup can be created,
    assigned, and completed today (no batching involved) while still
    being attachable to a batch once that feature is actually built -
    adding batching later means filling in `batch`, never a schema
    change or a rewrite of this model.
    """

    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name="pickup_tasks")

    batch = models.ForeignKey(
        CollectionBatch, on_delete=models.SET_NULL, null=True, blank=True, related_name="pickup_tasks",
    )

    rider = models.ForeignKey(
        RiderProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="pickup_tasks",
    )

    status = models.CharField(max_length=20, choices=PickupTaskStatus.choices, default=PickupTaskStatus.PENDING)

    # Plain ops fields - deliberately NOT auto-filled from SellerKYC, see
    # module docstring. Left blank/manual for now.
    pickup_address = models.CharField(max_length=255, blank=True)
    pickup_contact_phone = models.CharField(max_length=20, blank=True)

    requested_at = models.DateTimeField(auto_now_add=True)
    collected_at = models.DateTimeField(null=True, blank=True)

    exception_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "logistics_pickup_tasks"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Pickup {self.package.reference} ({self.get_status_display()})"


class RiderAssignment(BaseModel):
    """
    One shared "a rider is/was assigned to X" record for any assignable
    thing (PickupTask, CollectionBatch, or DeliveryTask), via a generic
    FK - same pattern as apps.kyc.models.KYCAuditLog - instead of three
    near-identical assignment tables. This is what a future dispatch
    algorithm would create automatically; today nothing creates these
    except the manual assign_rider_to_* helpers in
    apps.logistics.services.
    """

    rider = models.ForeignKey(RiderProfile, on_delete=models.CASCADE, related_name="assignments")

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    assigned_to = GenericForeignKey("content_type", "object_id")

    status = models.CharField(
        max_length=20, choices=RiderAssignmentStatus.choices, default=RiderAssignmentStatus.OFFERED,
    )

    offered_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "logistics_rider_assignments"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["content_type", "object_id"])]

    def __str__(self):
        return f"{self.rider} -> {self.assigned_to} ({self.get_status_display()})"


class DeliveryTask(BaseModel):
    """
    The rider's side of an existing apps.delivery.Delivery. Kept as its
    own model rather than adding rider fields directly onto Delivery, so
    the customer-facing Delivery/DeliveryUpdate tracking (already built
    and in use) never has to change shape as the rider side grows later.

    One per Delivery, local-delivery orders only - shipping orders go to
    a carrier, not a rider, and never get one (see
    apps.logistics.services.create_delivery_task_for_local_delivery).
    """

    delivery = models.OneToOneField(
        "delivery.Delivery", on_delete=models.CASCADE, related_name="delivery_task",
    )

    batch = models.ForeignKey(
        CollectionBatch, on_delete=models.SET_NULL, null=True, blank=True, related_name="delivery_tasks",
    )

    rider = models.ForeignKey(
        RiderProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="delivery_tasks",
    )

    # Which collected packages this delivery run is actually carrying -
    # this is the "final delivery mapping back to each fulfillment" the
    # spec's future-support list asks for, expressed as a plain M2M
    # rather than anything computed.
    packages = models.ManyToManyField(Package, related_name="delivery_tasks", blank=True)

    status = models.CharField(max_length=20, choices=DeliveryTaskStatus.choices, default=DeliveryTaskStatus.PENDING)

    delivered_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "logistics_delivery_tasks"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Delivery task for {self.delivery.order.reference} ({self.get_status_display()})"


class RouteActivity(BaseModel):
    """
    Ordered stop list within a CollectionBatch - the "Route/activity"
    concept from the spec. Each row is either a pickup stop or a
    delivery stop. Sequencing is a plain manual integer for now; nothing
    computes an optimal route yet - that's future work this table is
    shaped to accept without a migration.
    """

    batch = models.ForeignKey(CollectionBatch, on_delete=models.CASCADE, related_name="route_activities")

    sequence = models.PositiveIntegerField()

    activity_type = models.CharField(max_length=20, choices=RouteActivityType.choices)

    pickup_task = models.ForeignKey(
        PickupTask, on_delete=models.CASCADE, null=True, blank=True, related_name="route_activities",
    )
    delivery_task = models.ForeignKey(
        DeliveryTask, on_delete=models.CASCADE, null=True, blank=True, related_name="route_activities",
    )

    status = models.CharField(
        max_length=20, choices=RouteActivityStatus.choices, default=RouteActivityStatus.PENDING,
    )

    arrived_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "logistics_route_activities"
        ordering = ["batch", "sequence"]
        constraints = [
            models.UniqueConstraint(fields=["batch", "sequence"], name="unique_batch_sequence"),
        ]

    def __str__(self):
        return f"Batch {str(self.batch_id)[:8]} - stop {self.sequence} ({self.activity_type})"
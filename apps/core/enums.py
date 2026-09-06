from django.db import models


class Status(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"


class UserRole(models.TextChoices):
    CUSTOMER = "CUSTOMER", "Customer"
    ADMIN = "ADMIN", "Administrator"
    STAFF = "STAFF", "Staff"
    SELLER = "SELLER", "Seller"
    AFFILIATE = "AFFILIATE", "Affiliate"


class PaymentStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    PAID = "PAID", "Paid"
    FAILED = "FAILED", "Failed"
    REFUNDED = "REFUNDED", "Refunded"


class OrderStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    PROCESSING = "PROCESSING", "Processing"
    COMPLETED = "COMPLETED", "Completed"
    CANCELLED = "CANCELLED", "Cancelled"


class DeliveryMethod(models.TextChoices):
    SHIPPING = "shipping", "Shipping"
    LOCAL_DELIVERY = "local_delivery", "Local Delivery"


class PayoutStatus(models.TextChoices):
    """
    Shared by SellerPayout and AffiliatePayout (Phase 9, spec sections
    19/20) - both payout flows are structurally identical, so they share
    one status set rather than duplicating it per app.
    """

    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    PAID = "paid", "Paid"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"


class FulfillmentStatus(models.TextChoices):
    """
    Per-OrderItem fulfillment state, owned by whichever seller sold that
    line item - deliberately separate from Order.status (which tracks the
    customer's payment/checkout state as a whole). One Order can have
    items from several sellers, each progressing independently: Seller A
    might ship their item while Seller B is still preparing theirs.
    """

    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    SHIPPED = "shipped", "Shipped"
    DELIVERED = "delivered", "Delivered"
    CANCELLED = "cancelled", "Cancelled"


class DeliveryStatus(models.TextChoices):
    """
    Unified status set covering both methods - but the two methods use
    different subsets and different starting points (see
    apps.delivery.services for the per-method allowed progression).

    Local delivery deliberately skips READY_FOR_SHIPPING/SHIPPED/
    IN_TRANSIT entirely - those are shipping-carrier concepts that don't
    apply when a rider is just bringing the order across town. Local
    delivery goes straight from PREPARING to OUT_FOR_DELIVERY, so it
    always looks and feels closer/faster than a shipped order at the
    same real-world stage.
    """

    ORDER_CONFIRMED = "order_confirmed", "Order Confirmed"
    PREPARING = "preparing", "Preparing"
    READY_FOR_SHIPPING = "ready_for_shipping", "Ready for Shipping"   # shipping only
    SHIPPED = "shipped", "Shipped"                                    # shipping only
    IN_TRANSIT = "in_transit", "In Transit"                           # shipping only
    OUT_FOR_DELIVERY = "out_for_delivery", "Out for Delivery"
    DELIVERED = "delivered", "Delivered"
    FAILED_DELIVERY = "failed_delivery", "Delivery Failed"
    CANCELLED = "cancelled", "Cancelled"

class RefundStatus(models.TextChoices):
    REQUESTED = "requested", "Requested"
    REJECTED = "rejected", "Rejected"
    PROCESSING = "processing", "Processing"
    PROCESSED = "processed", "Processed"
    FAILED = "failed", "Failed"

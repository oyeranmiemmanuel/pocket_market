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
    RIDER = "RIDER", "Delivery Rider"

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
    """
    Spec sections 25-27's full return/refund lifecycle. Physical items
    go through the return-tracking states (RETURN_IN_PROGRESS ->
    ITEM_RECEIVED -> SELLER_CONDITION_CONFIRMED); digital items have
    nothing to physically return, so they skip straight from
    UNDER_REVIEW to PLATFORM_APPROVED (see apps.orders.services.refunds).
    REJECTED is reachable from any pre-approval state. PLATFORM_APPROVED
    starts the mandatory delay (REFUND_PROCESSING_DELAY_MINUTES) before
    PROCESSING can begin - see begin_refund_processing.
    """
    REQUESTED = "requested", "Requested"
    UNDER_REVIEW = "under_review", "Under Review"
    RETURN_IN_PROGRESS = "return_in_progress", "Return In Progress"
    ITEM_RECEIVED = "item_received", "Item Received"
    SELLER_CONDITION_CONFIRMED = "seller_condition_confirmed", "Seller Condition Confirmed"
    PLATFORM_APPROVED = "platform_approved", "Platform Approved"
    PROCESSING = "processing", "Processing"
    PROCESSED = "processed", "Refunded"
    REJECTED = "rejected", "Rejected"
    FAILED = "failed", "Failed"


class RefundReasonCategory(models.TextChoices):
    """Spec section 25 - the buyer picks one of these, then adds free-text explanation separately."""
    NOT_AS_DESCRIBED = "not_as_described", "Item not as described"
    DAMAGED = "damaged", "Arrived damaged"
    WRONG_ITEM = "wrong_item", "Wrong item received"
    NOT_DELIVERED = "not_delivered", "Never arrived"
    CHANGED_MIND = "changed_mind", "Changed my mind"
    OTHER = "other", "Other"


class KYCStatus(models.TextChoices):
    """
    Shared by BuyerKYC/SellerKYC/AffiliateKYC/RiderKYC (apps.kyc) - one
    status set for all four subject types, the same way PayoutStatus is
    shared between SellerPayout/AffiliatePayout above. Deliberately NOT
    the same set as SellerStatus/AffiliateStatus/RiderStatus: those track
    "is this account allowed to trade/deliver"; this tracks "have we
    collected and confirmed this party's KYC information" - two
    lifecycles the phase-1 spec keeps intentionally decoupled.
    """

    NOT_SUBMITTED = "not_submitted", "Not Submitted"
    SUBMITTED = "submitted", "Submitted"
    UNDER_REVIEW = "under_review", "Under Review"
    CONFIRMED = "confirmed", "Confirmed"
    REJECTED = "rejected", "Rejected"
    RESUBMISSION = "resubmission", "Resubmission Required"
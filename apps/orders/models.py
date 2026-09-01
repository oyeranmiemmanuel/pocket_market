from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.catalog.models import Product
from apps.core.enums import DeliveryMethod, FulfillmentStatus
from apps.core.models import BaseModel


class OrderStatus(models.TextChoices):
    PENDING = "pending", "Pending Payment"
    PAID = "paid", "Paid"
    SHIPPED = "shipped", "Shipped"
    DELIVERED = "delivered", "Delivered"
    CANCELLED = "cancelled", "Cancelled"
    FAILED = "failed", "Payment Failed"


class Order(BaseModel):
    """
    Real multi-item order, built from a Cart at checkout time.

    Distinct from the older apps.Order (single-product, still used by the
    legacy buy_now/checkout flow) - this is the one 14_ORDERS.md /
    13_CHECKOUT.md describe. The two aren't merged yet; see docs/28_DECISIONS.md.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="new_orders",
    )

    delivery_method = models.CharField(
        max_length=20,
        choices=DeliveryMethod.choices,
        default=DeliveryMethod.SHIPPING,
        help_text="Chosen at checkout; used to build the right tracking "
                   "pipeline once payment succeeds (see apps.delivery).",
    )

    reference = models.CharField(max_length=100, unique=True)

    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING,
    )

    # Snapshot contact info at time of order, independent of the user's
    # current profile - so a later profile edit never rewrites history.
    email = models.EmailField()
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20)

    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    shipping_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)

    # Phase 7 - affiliate attribution, snapshotted at checkout time from
    # apps.affiliates.services.get_attributed_affiliate(request) (the
    # "last valid affiliate click" cookie - spec section 27). Snapshotting
    # here, rather than resolving it fresh from the cookie later, means a
    # later click/cookie expiry/affiliate suspension never rewrites which
    # affiliate a *past* order was attributed to. `affiliate_code` is kept
    # alongside the FK (not derived from it) so the code is still visible
    # even if the affiliate profile is later deleted (SET_NULL).
    affiliate = models.ForeignKey(
        "affiliates.AffiliateProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attributed_orders",
        help_text="Affiliate credited with referring this order, if any.",
    )
    affiliate_code = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order {self.reference} ({self.get_status_display()})"

    @property
    def is_paid(self):
        return self.status in (OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.DELIVERED)


class OrderItem(BaseModel):
    """
    Line item. Price/name snapshotted at purchase time so later product
    price changes or renames never alter historical orders.
    """

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")

    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        related_name="order_items",
    )

    # Snapshotted at checkout (see apps.orders.services.checkout) from
    # product.seller, per docs - one Order can contain items from several
    # sellers, so ownership lives on the line item, not the Order. Kept
    # even if the product is later reassigned/deleted, so historical
    # orders always show who actually sold this line item.
    seller = models.ForeignKey(
        "sellers.SellerProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
        help_text="Null = this was a platform-owned product (no seller).",
    )

    product_name = models.CharField(max_length=200)

    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    # Snapshot of apps.sellers.services.resolve_commission_rate(product) at
    # checkout time - the percentage the PLATFORM keeps from this line
    # item. Frozen here so a later change to the seller's or product's
    # commission rate never rewrites the financial history of past
    # orders. This is a snapshot for display only; the actual payable
    # ledger (gross/commission/refund/net per line item) is a later
    # phase - see docs/28_DECISIONS.md.
    platform_commission_rate = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
    )

    # Independent of Order.status (payment/checkout state). Each seller
    # advances only the items that belong to them.
    fulfillment_status = models.CharField(
        max_length=20,
        choices=FulfillmentStatus.choices,
        default=FulfillmentStatus.PENDING,
    )

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.quantity} x {self.product_name}"

    @property
    def subtotal(self):
        return self.unit_price * self.quantity

    @property
    def estimated_seller_earning(self):
        """
        Informational only (not a ledger entry) - what this line item
        would net the seller based on the snapshotted commission rate.
        Platform-owned items (no seller) never earn anything here.
        """
        if self.seller_id is None or self.platform_commission_rate is None:
            return None
        return (self.subtotal * (100 - self.platform_commission_rate) / 100).quantize(
            self.unit_price
        )


class ShippingAddress(BaseModel):
    """One shipping address per order, captured at checkout."""

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="shipping_address")

    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, default="Nigeria")

    def __str__(self):
        return f"{self.address_line1}, {self.city}"
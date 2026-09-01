from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel

class SellerStatus(models.TextChoices):
    PENDING = "pending", "Pending Review"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    SUSPENDED = "suspended", "Suspended"


class SellerProfile(BaseModel):
    """
    A seller is a CUSTOMER account with an approved store attached, not a
    separate account type - a user can be a customer, a seller, and an
    affiliate all at once. Access to seller features is gated on
    status == APPROVED, not on User.role (see apps.sellers.permissions).
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="seller_profile",
    )

    store_name = models.CharField(max_length=150)

    store_slug = models.SlugField(max_length=170, unique=True, blank=True)

    store_description = models.TextField(blank=True)

    logo = models.ImageField(upload_to="sellers/logos/", blank=True, null=True)

    banner = models.ImageField(upload_to="sellers/banners/", blank=True, null=True)

    phone = models.CharField(max_length=20)

    business_email = models.EmailField()

    status = models.CharField(
        max_length=20,
        choices=SellerStatus.choices,
        default=SellerStatus.PENDING,
    )

    rejection_reason = models.TextField(blank=True)

    # Per-seller override of the platform default (core.constants).
    # Null = use the platform default rate.
    commission_rate = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Percentage platform takes from this seller's sales. "
                   "Leave blank to use the platform default.",
    )

    # Phase 7 - middle rung of the affiliate commission hierarchy (spec
    # section 16): Product.affiliate_commission_rate ->
    # SellerProfile.affiliate_commission_rate ->
    # PLATFORM_AFFILIATE_COMMISSION_RATE_DEFAULT. Separate from
    # `commission_rate` above, which is the platform's own cut and has
    # nothing to do with affiliates.
    affiliate_commission_rate = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Affiliate commission percentage applied to this "
                   "seller's products by default (unless a product "
                   "overrides it). Leave blank to use the platform default.",
    )

    bank_name = models.CharField(max_length=100, blank=True)
    bank_account_number = models.CharField(max_length=20, blank=True)
    bank_account_name = models.CharField(max_length=150, blank=True)

    reviewed_at = models.DateTimeField(null=True, blank=True)

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="seller_reviews",
    )

    class Meta:
        db_table = "seller_profiles"
        verbose_name = "Seller Profile"
        verbose_name_plural = "Seller Profiles"

    def __str__(self):
        return f"{self.store_name} ({self.get_status_display()})"

    @property
    def is_approved(self):
        return self.status == SellerStatus.APPROVED


        # ------------------------------------------------------------------
    # Phase 8 - financial ledger. Balances are never computed as
    # "total_orders - commissions" (spec section 18 explicitly warns
    # against that) - they're always aggregated straight from SellerEarning
    # rows, the same pattern AffiliateProfile already uses for its own
    # earnings properties.
    # ------------------------------------------------------------------

    def _earning_sum(self, *statuses):
        return self.earnings.filter(status__in=statuses).aggregate(
            total=models.Sum("earning_amount")
        )["total"] or Decimal("0.00")

    @property
    def total_earnings(self):
        """Everything ever credited to this seller, excluding cancelled/reversed earnings and the reversal rows themselves."""
        return self._earning_sum(
            EarningStatus.PENDING, EarningStatus.CONFIRMED,
            EarningStatus.AVAILABLE, EarningStatus.PAID,
        )

    @property
    def pending_earnings(self):
        """Not yet cleared for payout - still within the refund/hold window."""
        return self._earning_sum(EarningStatus.PENDING, EarningStatus.CONFIRMED)

    @property
    def available_earnings(self):
        """Cleared and ready to be requested as a payout (Phase 9)."""
        return self._earning_sum(EarningStatus.AVAILABLE)

    @property
    def paid_earnings(self):
        return self._earning_sum(EarningStatus.PAID)

    @property
    def total_sales(self):
        """Gross value of every original (non-reversal) earning that isn't cancelled - what the seller dashboard calls "Total Sales"."""
        return self.earnings.filter(reversal_of__isnull=True).exclude(
            status=EarningStatus.CANCELLED
        ).aggregate(total=models.Sum("order_amount"))["total"] or Decimal("0.00")

    @property
    def refunded_amount(self):
        """Gross value of every original earning that has since been reversed by a refund."""
        return self.earnings.filter(
            reversal_of__isnull=True, status=EarningStatus.REVERSED,
        ).aggregate(total=models.Sum("order_amount"))["total"] or Decimal("0.00")


class EarningStatus(models.TextChoices):
    """
    Mirrors apps.affiliates.models.CommissionStatus's lifecycle exactly,
    for the same reason: a seller's earning on a line item is never
    immediately payable - it only becomes AVAILABLE after whatever
    refund/hold period the platform decides on (manual, via admin, for
    now), and only PAID once an actual payout has gone out (Phase 9).
    """

    PENDING = "pending", "Pending"
    CONFIRMED = "confirmed", "Confirmed"
    AVAILABLE = "available", "Available"
    PAID = "paid", "Paid"
    CANCELLED = "cancelled", "Cancelled"
    REVERSED = "reversed", "Reversed"


class SellerEarning(BaseModel):
    """
    One row per (order_item, seller) - what the seller actually nets from
    one line item, after the platform's commission and any affiliate
    commission have been taken out. Created once, at payment-success
    time, by apps.ledger.services.process_order_financials (which also
    creates the matching AffiliateCommission and LedgerEntry rows from
    the exact same computed allocation) - never in a view, and never from
    client-supplied numbers (spec section 42).

    This closes the gap flagged after Phase 4: seller dashboard
    "earnings / pending payout / available balance" used to be
    placeholder text because there was nowhere to compute them from other
    than a live estimate. Now there's a real, auditable row per sale.

    Refunds are handled the same way AffiliateCommission handles them
    (spec section 25): the original row is never deleted or silently
    edited - a second row is created with `reversal_of` pointing back at
    it, and the original flips to REVERSED. No refund flow exists yet in
    this codebase to call this automatically (see docs/28_DECISIONS.md) -
    apps.sellers.services.reverse_seller_earning is here ready for
    whenever refunds are built, mirroring
    apps.affiliates.services.reverse_commission.
    """

    seller = models.ForeignKey(
        SellerProfile,
        on_delete=models.PROTECT,
        related_name="earnings",
        help_text="PROTECT, not SET_NULL/CASCADE - an earning must never "
                   "lose track of who it's owed to.",
    )

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="seller_earnings",
    )

    order_item = models.ForeignKey(
        "orders.OrderItem",
        on_delete=models.PROTECT,
        related_name="seller_earnings",
    )

    # Snapshots, frozen at creation time - a later change to the seller's/
    # product's commission rate must never rewrite a past earning's
    # numbers (same pattern as OrderItem.platform_commission_rate and
    # AffiliateCommission's snapshot fields).
    order_amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Gross line-item amount (OrderItem.subtotal) this earning was calculated from.",
    )
    platform_commission_rate = models.DecimalField(max_digits=5, decimal_places=2)
    platform_commission_amount = models.DecimalField(max_digits=12, decimal_places=2)
    affiliate_commission_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
        help_text="What was paid out to an affiliate on this same line "
                   "item, if any - shown for transparency; this amount "
                   "already came out of the seller's share, not the "
                   "platform's (spec section 17).",
    )
    earning_amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="What the seller actually nets: order_amount - platform_commission_amount - affiliate_commission_amount.",
    )

    status = models.CharField(
        max_length=20,
        choices=EarningStatus.choices,
        default=EarningStatus.PENDING,
    )

    reversal_of = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reversals",
        help_text="Set only on a reversal row - points back at the "
                   "original earning it cancels out.",
    )

    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "seller_earnings"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["seller", "status"]),
            models.Index(fields=["order", "status"]),
        ]
        constraints = [
            # One *original* earning per order item - reversals are
            # exempt (they intentionally reference the same order_item as
            # the row they're cancelling), so this only guards against
            # accidentally creating the original twice (e.g. a webhook
            # firing twice - see spec section 39, idempotency).
            models.UniqueConstraint(
                fields=["order_item"],
                condition=models.Q(reversal_of__isnull=True),
                name="unique_original_earning_per_order_item",
            ),
        ]

    def __str__(self):
        return f"{self.seller} earns {self.earning_amount} on {self.order_item} ({self.get_status_display()})"
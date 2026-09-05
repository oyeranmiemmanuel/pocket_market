from decimal import Decimal
from apps.core.enums import PayoutStatus
from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.core.models import BaseModel


class AffiliateStatus(models.TextChoices):
    PENDING = "pending", "Pending Review"
    ACTIVE = "active", "Active"
    REJECTED = "rejected", "Rejected"
    SUSPENDED = "suspended", "Suspended"


class AffiliateProfile(BaseModel):
    """
    Like SellerProfile, this is a capability attached to a CUSTOMER
    account, not a separate account type - a user can be a customer,
    seller, and affiliate all at once. Access gated on
    status == ACTIVE (see apps.affiliates.permissions), never on
    User.role.

    Phase 5 scope only: profile + application + admin approval.
    Referral tracking (AffiliateLink/AffiliateClick) and commission
    calculation on purchase are explicitly out of scope here - later
    phases, per docs/28_DECISIONS.md.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="affiliate_profile",
    )

    affiliate_code = models.CharField(max_length=20, unique=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=AffiliateStatus.choices,
        default=AffiliateStatus.PENDING,
    )

    rejection_reason = models.TextField(blank=True)

    commission_rate = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Percentage of a referred sale paid to this affiliate. "
                   "Leave blank to use the platform default.",
    )

    bank_code = models.CharField(
        max_length=10, blank=True,
        help_text="Paystack bank code - required to send this affiliate a payout.",
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
        related_name="affiliate_reviews",
    )

    class Meta:
        db_table = "affiliate_profiles"
        verbose_name = "Affiliate Profile"
        verbose_name_plural = "Affiliate Profiles"

    def __str__(self):
        return f"{self.affiliate_code or self.user} ({self.get_status_display()})"

    @property
    def is_active(self):
        return self.status == AffiliateStatus.ACTIVE

    @property
    def total_clicks(self):
        return self.clicks.count()

    @property
    def total_conversions(self):
        """Phase 7 - a click is flipped to converted=True by record_conversion_for_order() once it leads to a paid, attributed order."""
        return self.clicks.filter(converted=True).count()

    @property
    def conversion_rate(self):
        clicks = self.total_clicks
        if not clicks:
            return Decimal("0")
        return (Decimal(self.total_conversions) / Decimal(clicks) * 100).quantize(Decimal("0.01"))

    def _commission_sum(self, *statuses):
        return self.commissions.filter(status__in=statuses).aggregate(
            total=models.Sum("commission_amount")
        )["total"] or Decimal("0.00")

    @property
    def total_earnings(self):
        """Everything ever credited to this affiliate, excluding cancelled/reversed commissions and the reversal rows themselves."""
        return self._commission_sum(
            CommissionStatus.PENDING, CommissionStatus.CONFIRMED,
            CommissionStatus.AVAILABLE, CommissionStatus.PAID,
        )

    @property
    def pending_earnings(self):
        """Not yet cleared for payout - still within the refund/hold window."""
        return self._commission_sum(CommissionStatus.PENDING, CommissionStatus.CONFIRMED)

    @property
    def withdrawable_balance(self):
        """
        Cleared AVAILABLE commissions not already reserved by an
        unresolved payout request (Phase 9) - what this affiliate can
        actually request right now.
        """
        return self.commissions.filter(
            status=CommissionStatus.AVAILABLE, payout__isnull=True,
        ).aggregate(total=models.Sum("commission_amount"))["total"] or Decimal("0.00")

    @property
    def payouts_in_progress_total(self):
        """Sum of payouts this affiliate has requested that haven't resolved yet."""
        return self.payouts.filter(
            status__in=[PayoutStatus.PENDING, PayoutStatus.PROCESSING],
        ).aggregate(total=models.Sum("amount"))["total"] or Decimal("0.00")
    @property
    def available_earnings(self):
        """Cleared and ready to be requested as a payout (Phase 9)."""
        return self._commission_sum(CommissionStatus.AVAILABLE)

    @property
    def paid_earnings(self):
        return self._commission_sum(CommissionStatus.PAID)


class AffiliateLink(BaseModel):
    """
    A ready-to-share referral link for one (affiliate, product) pair -
    e.g. "generate a link for Nike Sneakers" from the affiliate's
    dashboard. `referral_code` mirrors `affiliate.affiliate_code` at
    creation time - all links from one affiliate currently share the same
    code (?ref=<code> identifies the affiliate; the product itself comes
    from the URL path, e.g. /products/nike-sneakers/?ref=EMMA123), but
    keeping it as its own field leaves room for true per-link codes later
    without a schema change.
    """

    affiliate = models.ForeignKey(
        AffiliateProfile,
        on_delete=models.CASCADE,
        related_name="links",
    )

    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="affiliate_links",
    )

    referral_code = models.CharField(max_length=20, editable=False)

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "affiliate_links"
        unique_together = ("affiliate", "product")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.referral_code} -> {self.product.name}"

    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = self.affiliate.affiliate_code
        super().save(*args, **kwargs)

    @property
    def target_url(self):
        """Relative URL only - combine with request.scheme/get_host in templates for a full copyable link."""
        return f"{reverse('catalog:product_detail', args=[self.product.slug])}?ref={self.referral_code}"

    @property
    def total_clicks(self):
        return self.clicks.count()
    @property
    def total_conversions(self):
        return self.commissions.filter(reversal_of__isnull=True).exclude(status="cancelled").count()

    @property
    def total_earnings(self):
        return self.commissions.filter(reversal_of__isnull=True).exclude(status="cancelled").aggregate(
            total=models.Sum("commission_amount")
        )["total"] or Decimal("0.00")

    @property
    def commission_rate(self):
        """Current effective rate for this (affiliate, product) pair - spec section 16's hierarchy."""
        from .services import resolve_affiliate_commission_rate
        return resolve_affiliate_commission_rate(product=self.product, affiliate=self.affiliate)


class AffiliateClick(BaseModel):
    """
    One recorded visit via ?ref=<code>. Deliberately does NOT store the
    visitor's IP address or any other identifying info (spec section 13:
    "Be careful with IP addresses and privacy... do not collect
    unnecessary personal information") - de-duplication uses the Django
    session key instead, which identifies a browser session, not a person.

    `converted` stays False here always - flipping it true on a
    successful attributed order is Phase 7 (commission calculation)
    territory, not this phase.
    """

    affiliate = models.ForeignKey(
        AffiliateProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clicks",
    )

    affiliate_link = models.ForeignKey(
        AffiliateLink,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clicks",
    )

    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="affiliate_clicks",
    )

    session_key = models.CharField(
        max_length=40,
        blank=True,
        help_text="Django session key of the visitor, used only to de-duplicate repeat clicks - not to identify a person.",
    )

    converted = models.BooleanField(
        default=False,
        help_text="Set True in a later phase once this click leads to a paid, attributed order.",
    )

    class Meta:
        db_table = "affiliate_clicks"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["affiliate", "created_at"]),
            models.Index(fields=["session_key", "product", "created_at"]),
        ]

    def __str__(self):
        return f"Click via {self.affiliate} on {self.product} at {self.created_at:%Y-%m-%d %H:%M}"


class CommissionStatus(models.TextChoices):
    """
    Per spec section 15. A commission is never immediately payable - it
    only becomes AVAILABLE after whatever refund/hold period the platform
    decides on (manual, via admin, for now - no automatic timer yet), and
    only PAID once an actual payout has gone out (Phase 9).
    """

    PENDING = "pending", "Pending"
    CONFIRMED = "confirmed", "Confirmed"
    AVAILABLE = "available", "Available"
    PAID = "paid", "Paid"
    CANCELLED = "cancelled", "Cancelled"
    REVERSED = "reversed", "Reversed"


class AffiliateCommission(BaseModel):
    """
    One row per (order_item, affiliate) - the conversion + commission
    record described in spec sections 14/15 combined into a single model,
    since every field of a "conversion" (order, affiliate, affiliate_link,
    order amount) is naturally just context for its "commission" (amount,
    status). Created once, at payment-success time, by
    apps.affiliates.services.record_conversion_for_order - never in a
    view, and never from client-supplied numbers (spec section 42).

    Refunds are handled by leaving the original row alone and creating a
    second row with `reversal_of` pointing back at it (spec section 25:
    "create a reversal rather than silently deleting the original
    commission") - so the ledger-adjacent history is always auditable.
    The refund flow itself doesn't exist yet in this codebase (no refund
    model/view - see docs/28_DECISIONS.md), so `reverse_commission()` in
    services.py is here ready for whenever that lands.
    """

    affiliate = models.ForeignKey(
        AffiliateProfile,
        on_delete=models.PROTECT,
        related_name="commissions",
        help_text="PROTECT, not SET_NULL/CASCADE - a commission must "
                   "never lose track of who it's owed to, even if we "
                   "later add affiliate deletion.",
    )

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="affiliate_commissions",
    )

    order_item = models.ForeignKey(
        "orders.OrderItem",
        on_delete=models.PROTECT,
        related_name="affiliate_commissions",
    )

    payout = models.ForeignKey(
        "AffiliatePayout",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="commissions",
        help_text="Set once this commission has been reserved by a "
                   "payout request (Phase 9) - null means it's still "
                   "unreserved AVAILABLE balance the affiliate could request.",
    )
    affiliate_link = models.ForeignKey(
        AffiliateLink,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="commissions",
        help_text="The link this conversion is credited through, if the "
                   "affiliate had generated one for this exact product. "
                   "Null doesn't invalidate the commission - attribution "
                   "is by affiliate code, not by a specific link.",
    )

    # Snapshots, frozen at creation time - a later change to the
    # affiliate's/product's/seller's rate must never rewrite a past
    # commission's numbers (same pattern as OrderItem.platform_commission_rate).
    order_amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Gross line-item amount (OrderItem.subtotal) this commission was calculated from.",
    )
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2)
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2)

    status = models.CharField(
        max_length=20,
        choices=CommissionStatus.choices,
        default=CommissionStatus.PENDING,
    )

    reversal_of = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reversals",
        help_text="Set only on a reversal row - points back at the "
                   "original commission it cancels out.",
    )

    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "affiliate_commissions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["affiliate", "status"]),
            models.Index(fields=["order", "status"]),
        ]
        constraints = [
            # One *original* commission per order item - reversals are
            # exempt (they intentionally reference the same order_item as
            # the row they're cancelling), so this only guards against
            # accidentally creating the original twice (e.g. a webhook
            # firing twice - see spec section 39, idempotency).
            models.UniqueConstraint(
                fields=["order_item"],
                condition=models.Q(reversal_of__isnull=True),
                name="unique_original_commission_per_order_item",
            ),
        ]

    def __str__(self):
        return f"{self.affiliate} earns {self.commission_amount} on {self.order_item} ({self.get_status_display()})"

class AffiliatePayout(BaseModel):
    """
    Phase 9 (spec section 20) - mirrors SellerPayout exactly. Created
    only through apps.affiliates.services.request_affiliate_payout,
    which reserves the exact AffiliateCommission rows this payout
    settles (see AffiliateCommission.payout).
    """

    affiliate = models.ForeignKey(
        AffiliateProfile,
        on_delete=models.PROTECT,
        related_name="payouts",
        help_text="PROTECT - a payout must never lose track of who requested it.",
    )

    amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="The exact sum of the AffiliateCommission rows this payout reserved.",
    )

    status = models.CharField(
        max_length=20,
        choices=PayoutStatus.choices,
        default=PayoutStatus.PENDING,
    )

    reference = models.CharField(max_length=100, unique=True)

    bank_name = models.CharField(max_length=100)
    bank_account_number = models.CharField(max_length=20)
    bank_account_name = models.CharField(max_length=150)
    bank_code = models.CharField(max_length=10, blank=True)
    provider_reference = models.CharField(
        max_length=100, blank=True,
        help_text="Paystack's transfer_code for this payout, once sent (Phase 10).",
    )


    processed_at = models.DateTimeField(null=True, blank=True)

    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "affiliate_payouts"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["affiliate", "status"]),
        ]

    def __str__(self):
        return f"{self.reference} - {self.affiliate} - {self.get_status_display()}"
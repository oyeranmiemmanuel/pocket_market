from decimal import Decimal

from django.db import models

from apps.core.constants import DEFAULT_CURRENCY
from apps.core.models import BaseModel


class LedgerEntryType(models.TextChoices):
    SALE = "sale", "Sale"
    REFUND = "refund", "Refund"


class LedgerEntry(BaseModel):
    """
    Spec section 18 - the internal financial ledger. Immutable, append-
    only audit trail: one SALE row is created per OrderItem at payment-
    success time (by process_order_financials in services.py), capturing
    the full gross/platform/seller/affiliate breakdown exactly as
    computed at that moment. A refund never edits that row - it appends a
    second REFUND row instead (see reverse_order_item_financials), so the
    ledger always shows both the original transaction and its reversal
    side by side (spec section 25/48).

    This is deliberately separate from SellerEarning/AffiliateCommission:
    those two are the *actionable* per-party rows that carry a payout
    status (pending/confirmed/available/paid/...); LedgerEntry is the
    read-only, single source of truth for "what actually happened
    financially on this order," independent of anyone's payout state.
    Balances should never be computed as `total_orders - commissions`
    (the spec explicitly warns against this) - use SellerEarning/
    AffiliateCommission aggregates for balances, and LedgerEntry for
    audit/reporting.
    """

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="ledger_entries",
    )

    order_item = models.ForeignKey(
        "orders.OrderItem",
        on_delete=models.PROTECT,
        related_name="ledger_entries",
    )

    entry_type = models.CharField(
        max_length=10,
        choices=LedgerEntryType.choices,
        default=LedgerEntryType.SALE,
    )

    gross_amount = models.DecimalField(max_digits=12, decimal_places=2)
    platform_commission_amount = models.DecimalField(max_digits=12, decimal_places=2)
    seller_earning_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    affiliate_commission_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    payment_processing_fee = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
        help_text="Paystack's own transaction fee, if/when that figure "
                   "is captured from the provider response. Zero for now - "
                   "no fee data is currently read from Paystack's "
                   "verify/webhook payload; this field exists so that can "
                   "be wired in later without a schema change.",
    )

    refund_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
        help_text="Non-zero only on a REFUND row.",
    )

    net_payable_amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="What this row sends out of the platform's own pocket "
                   "to external parties: seller_earning_amount + "
                   "affiliate_commission_amount. Negative on a REFUND row.",
    )

    currency = models.CharField(max_length=3, default=DEFAULT_CURRENCY)

    reference = models.CharField(
        max_length=100,
        help_text="The order's reference - not unique on its own, since "
                   "one order produces several rows (one per item, plus "
                   "any refund rows).",
    )

    related_entry = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="refund_entries",
        help_text="Set only on a REFUND row - points back at the "
                   "original SALE row it partially or fully reverses.",
    )

    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "ledger_entries"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["order", "entry_type"]),
            models.Index(fields=["reference"]),
        ]
        constraints = [
            # One SALE row per order item - refunds are exempt (they
            # reference the same order_item as the sale they reverse), so
            # this only guards against accidentally ledgering the same
            # sale twice (e.g. a webhook firing twice - spec section 39).
            models.UniqueConstraint(
                fields=["order_item"],
                condition=models.Q(entry_type=LedgerEntryType.SALE),
                name="unique_sale_entry_per_order_item",
            ),
        ]

    def __str__(self):
        return f"{self.get_entry_type_display()} - {self.reference} - {self.order_item_id}"
"""
Phase 8 - orchestrates the financial ledger. Single entry point
(process_order_financials) called once from
apps.payments.services._finalize_successful_payment, right after an
order is marked paid - creates the AffiliateCommission rows (Phase 7,
unchanged), the SellerEarning rows, and the LedgerEntry audit rows, all
from the same per-item allocation so the three never disagree about the
split.
"""

from decimal import Decimal

from django.db import transaction

from apps.core.constants import DEFAULT_CURRENCY

from .models import LedgerEntry, LedgerEntryType


@transaction.atomic
def process_order_financials(order):
    """
    Idempotent - safe to call more than once for the same order (e.g.
    the Paystack callback and webhook both racing to verify the same
    reference). Items that already have a SALE ledger entry are skipped
    entirely (they've already had their AffiliateCommission/SellerEarning/
    LedgerEntry rows created), so a repeat call never double-writes or
    double-credits anyone.
    """
    from apps.affiliates.services import (
        calculate_order_item_allocation,
        record_conversion_for_order,
        resolve_effective_affiliate,
    )
    from apps.sellers.services import record_seller_earning

    # Phase 7 - unchanged. Idempotent on its own via AffiliateCommission's
    # unique constraint.
    affiliate_commissions = record_conversion_for_order(order)

    affiliate = resolve_effective_affiliate(order)

    existing_ledgered_item_ids = set(
        LedgerEntry.objects.filter(
            order=order, entry_type=LedgerEntryType.SALE,
        ).values_list("order_item_id", flat=True)
    )

    seller_earnings = []
    ledger_entries = []

    for item in order.items.select_related("product", "seller").all():
        if item.product_id is None or item.pk in existing_ledgered_item_ids:
            continue

        allocation = calculate_order_item_allocation(order_item=item, affiliate=affiliate)

        if item.seller_id is not None:
            earning = record_seller_earning(order=order, order_item=item, allocation=allocation)
            seller_earnings.append(earning)

        entry = LedgerEntry.objects.create(
            order=order,
            order_item=item,
            entry_type=LedgerEntryType.SALE,
            gross_amount=allocation["gross"],
            platform_commission_amount=allocation["platform_amount"],
            seller_earning_amount=allocation["seller_amount"],
            affiliate_commission_amount=allocation["affiliate_amount"],
            payment_processing_fee=Decimal("0.00"),
            refund_amount=Decimal("0.00"),
            net_payable_amount=allocation["seller_amount"] + allocation["affiliate_amount"],
            currency=DEFAULT_CURRENCY,
            reference=order.reference,
        )
        ledger_entries.append(entry)

    return {
        "affiliate_commissions": affiliate_commissions,
        "seller_earnings": seller_earnings,
        "ledger_entries": ledger_entries,
    }


@transaction.atomic
def reverse_order_item_financials(*, order_item, reason=""):
    """
    Spec sections 18/25/48 - reverses everything tied to one order_item
    after a refund: the AffiliateCommission (if any), the SellerEarning
    (if any), and appends a REFUND LedgerEntry that mirrors the original
    SALE row with every amount negated, `related_entry` pointing back at
    it. Nothing is deleted or silently edited - both the original
    transaction and its reversal stay visible (spec section 18: "the
    ledger must preserve the original transaction and reversal").

    Full-item reversal only, for now - no refund flow/model exists yet in
    this codebase to call this automatically (see docs/28_DECISIONS.md).
    A partial-refund `refund_amount` parameter can be added later without
    changing this function's shape.

    Idempotent: if the SALE row for this item has already been reversed
    (a REFUND row with related_entry pointing at it already exists),
    this is a no-op that returns the existing refund entry rather than
    creating a second one.
    """
    from apps.affiliates.models import AffiliateCommission
    from apps.affiliates.services import reverse_commission
    from apps.sellers.services import reverse_seller_earning

    sale_entry = LedgerEntry.objects.filter(
        order_item=order_item, entry_type=LedgerEntryType.SALE,
    ).first()
    if sale_entry is None:
        return None  # this item was never ledgered (e.g. no product) - nothing to reverse

    existing_refund = LedgerEntry.objects.filter(related_entry=sale_entry).first()
    if existing_refund is not None:
        return existing_refund  # already reversed - idempotent

    commission = AffiliateCommission.objects.filter(
        order_item=order_item, reversal_of__isnull=True,
    ).exclude(status="cancelled").first()
    if commission is not None:
        reverse_commission(commission=commission, reason=reason)

    earning = order_item.seller_earnings.filter(reversal_of__isnull=True).exclude(
        status="cancelled"
    ).first()
    if earning is not None:
        reverse_seller_earning(earning=earning, reason=reason)

    refund_entry = LedgerEntry.objects.create(
        order=order_item.order,
        order_item=order_item,
        entry_type=LedgerEntryType.REFUND,
        gross_amount=-sale_entry.gross_amount,
        platform_commission_amount=-sale_entry.platform_commission_amount,
        seller_earning_amount=-sale_entry.seller_earning_amount,
        affiliate_commission_amount=-sale_entry.affiliate_commission_amount,
        payment_processing_fee=Decimal("0.00"),
        refund_amount=sale_entry.gross_amount,
        net_payable_amount=-sale_entry.net_payable_amount,
        currency=sale_entry.currency,
        reference=sale_entry.reference,
        related_entry=sale_entry,
        notes=reason,
    )
    return refund_entry
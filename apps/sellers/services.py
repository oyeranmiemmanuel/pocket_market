"""
Seller application lifecycle + commission rate resolution.
"""
from django.conf import settings

from apps.core.enums import PayoutStatus
from apps.core.utils import generate_reference
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.core.constants import PLATFORM_COMMISSION_RATE_DEFAULT
from apps.core.exceptions import ValidationFailedError
from apps.core.utils import unique_slugify

from .models import EarningStatus, SellerEarning, SellerPayout, SellerProfile, SellerStatus
def apply_for_seller(*, user, store_name, store_description, phone, business_email):
    """
    Create a pending seller application. One per user - raises if they
    already have a profile (regardless of its current status), so a
    rejected/suspended seller can't just spam new applications; that
    should go through re-review of the existing profile instead.
    """
    if SellerProfile.objects.filter(user=user).exists():
        raise ValidationFailedError("You already have a seller application on file.")

    profile = SellerProfile.objects.create(
        user=user,
        store_name=store_name,
        store_slug=unique_slugify(SellerProfile(), store_name, slug_field="store_slug"),
        store_description=store_description,
        phone=phone,
        business_email=business_email,
        status=SellerStatus.PENDING,
    )
    return profile


def approve_seller(*, profile, reviewed_by):
    profile.status = SellerStatus.APPROVED
    profile.reviewed_at = timezone.now()
    profile.reviewed_by = reviewed_by
    profile.rejection_reason = ""
    profile.save(update_fields=["status", "reviewed_at", "reviewed_by", "rejection_reason"])
    return profile


def reject_seller(*, profile, reviewed_by, reason=""):
    profile.status = SellerStatus.REJECTED
    profile.reviewed_at = timezone.now()
    profile.reviewed_by = reviewed_by
    profile.rejection_reason = reason
    profile.save(update_fields=["status", "reviewed_at", "reviewed_by", "rejection_reason"])
    return profile


def suspend_seller(*, profile, reviewed_by, reason=""):
    profile.status = SellerStatus.SUSPENDED
    profile.reviewed_at = timezone.now()
    profile.reviewed_by = reviewed_by
    profile.rejection_reason = reason
    profile.save(update_fields=["status", "reviewed_at", "reviewed_by", "rejection_reason"])
    return profile


def resolve_commission_rate(product) -> Decimal:
    """
    Product.commission_rate -> Seller.commission_rate -> platform default.
    Platform-owned products (no seller) always resolve to 100% - there's
    no seller to pay out, the whole sale is the platform's.
    """
    if product.seller_id is None:
        return Decimal("100")

    if product.commission_rate is not None:
        return product.commission_rate

    if product.seller.commission_rate is not None:
        return product.seller.commission_rate

    return Decimal(PLATFORM_COMMISSION_RATE_DEFAULT)


# ---------------------------------------------------------------------------
# Phase 8 - financial ledger (seller side).
#
# record_seller_earning is called once per seller-owned OrderItem by
# apps.ledger.services.process_order_financials, right after that item's
# full gross/platform/affiliate/seller allocation has already been
# computed by apps.affiliates.services.calculate_order_item_allocation -
# so the amount recorded here always agrees with what the ledger and any
# affiliate commission on the same item say, instead of three different
# places quietly computing the split three different ways.
# ---------------------------------------------------------------------------

def record_seller_earning(*, order, order_item, allocation):
    """
    Create the SellerEarning row for one seller-owned order_item from a
    precomputed allocation dict (see calculate_order_item_allocation).
    Idempotent only in the sense that a repeat call for an order_item
    that already has one raises IntegrityError (the unique constraint) -
    the caller (apps.ledger.services.process_order_financials) is
    responsible for never calling this twice for the same item; it
    already skips items it's previously ledgered.
    """
    return SellerEarning.objects.create(
        seller=order_item.seller,
        order=order,
        order_item=order_item,
        order_amount=allocation["gross"],
        platform_commission_rate=allocation["platform_commission_rate"],
        platform_commission_amount=allocation["platform_amount"],
        affiliate_commission_amount=allocation["affiliate_amount"],
        earning_amount=allocation["seller_amount"],
        status=EarningStatus.PENDING,
    )


def confirm_seller_earning(*, earning):
    """PENDING -> CONFIRMED. Manual admin step for now (no automatic timer) - mirrors apps.affiliates.services.confirm_commission."""
    earning.status = EarningStatus.CONFIRMED
    earning.save(update_fields=["status", "updated_at"])
    return earning


def mark_seller_earning_available(*, earning):
    """CONFIRMED -> AVAILABLE, i.e. cleared for payout (consumed by Phase 9)."""
    earning.status = EarningStatus.AVAILABLE
    earning.save(update_fields=["status", "updated_at"])
    return earning


def cancel_seller_earning(*, earning, reason=""):
    """Any pre-PAID status -> CANCELLED - used when an earning should never have existed (e.g. fraud found after the fact)."""
    earning.status = EarningStatus.CANCELLED
    if reason:
        earning.notes = reason
    earning.save(update_fields=["status", "notes", "updated_at"])
    return earning


@transaction.atomic
def reverse_seller_earning(*, earning, reason=""):
    """
    Spec section 25 - a refund on an already CONFIRMED/AVAILABLE/PAID
    earning doesn't delete or silently edit it; it creates a second,
    negative-of-the-original row (`reversal_of` pointing back) and flips
    the original to REVERSED, so both the original grant and its reversal
    stay visible in the seller's history. Mirrors
    apps.affiliates.services.reverse_commission exactly. No refund flow
    exists yet in this codebase to call this automatically (see
    docs/28_DECISIONS.md) - it's here ready for whenever refunds are
    built (see also apps.ledger.services.reverse_order_item_financials,
    which calls this alongside reverse_commission and records the
    matching ledger refund entry).
    """
    if earning.status == EarningStatus.REVERSED:
        return earning  # already reversed - idempotent

    reversal = SellerEarning.objects.create(
        seller=earning.seller,
        order=earning.order,
        order_item=earning.order_item,
        order_amount=earning.order_amount,
        platform_commission_rate=earning.platform_commission_rate,
        platform_commission_amount=earning.platform_commission_amount,
        affiliate_commission_amount=earning.affiliate_commission_amount,
        earning_amount=-earning.earning_amount,
        status=EarningStatus.REVERSED,
        reversal_of=earning,
        notes=reason,
    )

    earning.status = EarningStatus.REVERSED
    earning.save(update_fields=["status", "updated_at"])

    return reversal

# ---------------------------------------------------------------------------
# Phase 9 - seller payouts (spec section 19).
# ---------------------------------------------------------------------------

@transaction.atomic
def request_seller_payout(*, seller, amount):
    """
    A seller requests a payout of part or all of their withdrawable
    balance. Validates:
      - the seller has bank details on file (nothing to pay out to otherwise)
      - amount is positive and meets the configurable minimum withdrawal
      - amount does not exceed the seller's current withdrawable balance

    Reserves whichever AVAILABLE, not-yet-reserved earnings (oldest
    first) cover at least `amount`, linking them to the new SellerPayout
    via SellerEarning.payout. Earnings stay AVAILABLE (not PAID) until
    the payout actually completes - see mark_seller_payout_paid.

    Because earnings can't be split, the amount actually reserved (and
    therefore the payout's real `amount`) may be slightly more than what
    was requested - reserved rows always cover >= the requested amount,
    snapped to whole earning rows, so every payout stays traceable to an
    exact, auditable set of SellerEarning rows.
    """
    if amount is None or amount <= 0:
        raise ValidationFailedError("Enter a valid amount to withdraw.")

    if not (seller.bank_name and seller.bank_account_number and seller.bank_account_name):
        raise ValidationFailedError("Add your bank details before requesting a payout.")

    minimum = Decimal(settings.MINIMUM_SELLER_WITHDRAWAL)
    if amount < minimum:
        raise ValidationFailedError(f"The minimum withdrawal amount is \u20a6{minimum}.")

    withdrawable = seller.withdrawable_balance
    if amount > withdrawable:
        raise ValidationFailedError(
            f"You can only withdraw up to your available balance of \u20a6{withdrawable}."
        )

    candidates = (
        seller.earnings.select_for_update()
        .filter(status=EarningStatus.AVAILABLE, payout__isnull=True)
        .order_by("created_at")
    )

    reserved_ids = []
    running_total = Decimal("0.00")
    for earning in candidates:
        if running_total >= amount:
            break
        reserved_ids.append(earning.pk)
        running_total += earning.earning_amount

    if running_total < amount:
        # Balance moved between the check above and the row lock (e.g. a
        # concurrent request racing this one) - fail safe rather than
        # reserve short.
        raise ValidationFailedError("Your available balance changed - please try again.")

    payout = SellerPayout.objects.create(
        seller=seller,
        amount=running_total,
        reference=generate_reference("SPO"),
        bank_name=seller.bank_name,
        bank_code=seller.bank_code,          # <-- new line
        bank_account_number=seller.bank_account_number,
        bank_account_name=seller.bank_account_name,
        status=PayoutStatus.PENDING,
    )

    SellerEarning.objects.filter(pk__in=reserved_ids).update(payout=payout)

    return payout


def mark_seller_payout_processing(*, payout):
    """PENDING -> PROCESSING - admin has kicked off the actual bank transfer."""
    payout.status = PayoutStatus.PROCESSING
    payout.save(update_fields=["status", "updated_at"])
    return payout


@transaction.atomic
def mark_seller_payout_paid(*, payout):
    """
    -> PAID. The SellerEarning rows this payout reserved move from
    AVAILABLE to PAID at the same moment, so a seller's earnings history
    and payout history always agree about what's actually been settled.
    """
    payout.status = PayoutStatus.PAID
    payout.processed_at = timezone.now()
    payout.save(update_fields=["status", "processed_at", "updated_at"])

    payout.earnings.filter(status=EarningStatus.AVAILABLE).update(status=EarningStatus.PAID)
    return payout


def mark_seller_payout_failed(*, payout, reason=""):
    """
    -> FAILED. Releases the reserved earnings back to the unreserved
    AVAILABLE pool (spec section 19: "Do not immediately mark
    withdrawals as paid unless the payout operation actually succeeds")
    so the seller can request a payout again.
    """
    payout.status = PayoutStatus.FAILED
    if reason:
        payout.notes = reason
    payout.save(update_fields=["status", "notes", "updated_at"])
    payout.earnings.update(payout=None)
    return payout


def cancel_seller_payout(*, payout, reason=""):
    """PENDING/PROCESSING -> CANCELLED. Same release behaviour as a failure."""
    payout.status = PayoutStatus.CANCELLED
    if reason:
        payout.notes = reason
    payout.save(update_fields=["status", "notes", "updated_at"])
    payout.earnings.update(payout=None)
    return payout

@transaction.atomic
def send_seller_payout(*, payout):
    """
    Phase 10 - triggers the real Paystack transfer for a PENDING payout.
    Creates a transfer recipient from the payout's own snapshotted bank
    details, then initiates the transfer using the payout's `reference`
    as Paystack's idempotency reference. Moves the payout to PROCESSING
    immediately; final settlement (PAID/FAILED) is driven only by the
    transfer.success/transfer.failed webhook - never assumed here (spec
    section 19: "Do not immediately mark withdrawals as paid unless the
    payout operation actually succeeds").
    """
    from apps.payments.services import create_transfer_recipient, initiate_transfer

    if payout.status != PayoutStatus.PENDING:
        raise ValidationFailedError("Only pending payouts can be sent.")

    recipient_code = create_transfer_recipient(
        name=payout.bank_account_name,
        account_number=payout.bank_account_number,
        bank_code=payout.bank_code,
    )

    response = initiate_transfer(
        recipient_code=recipient_code,
        amount=payout.amount,
        reference=payout.reference,
        reason=f"Payout {payout.reference} to {payout.seller.store_name}",
    )

    payout.status = PayoutStatus.PROCESSING
    payout.provider_reference = response.get("transfer_code", "")
    payout.save(update_fields=["status", "provider_reference", "updated_at"])
    return payout
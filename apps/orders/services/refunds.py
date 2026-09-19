"""
Customer refund requests through to the actual money-back-to-customer
step via Paystack - wired into the Phase 8 ledger reversal machinery
(apps.ledger.services.reverse_order_item_financials).

Spec sections 25-27's full lifecycle:

    REQUESTED -> UNDER_REVIEW -> [RETURN_IN_PROGRESS -> ITEM_RECEIVED ->
    SELLER_CONDITION_CONFIRMED] -> PLATFORM_APPROVED -> PROCESSING ->
    PROCESSED ("Refunded")

The three bracketed states only apply to a physical item that actually
needs to come back (Refund.requires_physical_return) - a digital item
has nothing to return, so start_review() effectively leaves it ready to
approve straight from UNDER_REVIEW. REJECTED is reachable from any
state before PLATFORM_APPROVED. FAILED is reachable only from
PROCESSING (a Paystack failure).

These functions enforce the STATE transitions only, not who's allowed
to trigger them - each caller (buyer/admin/seller view) checks that
separately, though the seller-facing ones also verify item ownership.
"""

from django.db import transaction
from django.utils import timezone

from apps.core.constants import REFUND_PROCESSING_DELAY_MINUTES
from apps.core.exceptions import ValidationFailedError
from apps.ledger.services import reverse_order_item_financials

from ..models import Refund, RefundStatus

_PRE_APPROVAL_STATUSES = (
    RefundStatus.REQUESTED, RefundStatus.UNDER_REVIEW, RefundStatus.RETURN_IN_PROGRESS,
    RefundStatus.ITEM_RECEIVED, RefundStatus.SELLER_CONDITION_CONFIRMED,
)

# "Already has an active request" - everything except a terminal state
# (REJECTED/FAILED) or one that's already fully refunded.
_ACTIVE_STATUSES = _PRE_APPROVAL_STATUSES + (RefundStatus.PLATFORM_APPROVED, RefundStatus.PROCESSING)


def request_refund(*, order_item, user, reason, reason_category, evidence_files=None):
    """
    One active request per item at a time - a rejected/failed one can be
    re-filed, an in-flight/succeeded one can't. `evidence_files` is an
    iterable of uploaded files (spec section 25's "upload permitted
    evidence") - optional, since not every issue has something to show.
    """
    if order_item.order.user_id != user.id:
        raise ValidationFailedError("This isn't your order.")

    if not order_item.order.is_paid:
        raise ValidationFailedError("This order hasn't been paid for, so there's nothing to refund.")

    if Refund.objects.filter(order_item=order_item, status__in=_ACTIVE_STATUSES).exists():
        raise ValidationFailedError("A refund has already been requested for this item.")

    refund = Refund.objects.create(
        order_item=order_item,
        requested_by=user,
        reason=reason,
        reason_category=reason_category,
        amount=order_item.subtotal,
        status=RefundStatus.REQUESTED,
    )

    from ..models import RefundEvidence
    for uploaded_file in (evidence_files or []):
        RefundEvidence.objects.create(refund=refund, file=uploaded_file, uploaded_by=user)

    return refund


def start_review(*, refund, reviewed_by):
    """
    REQUESTED -> UNDER_REVIEW (admin/platform action). A digital item
    has nothing to physically return, so the return-tracking states
    simply won't apply to it - approve_refund lets it go straight from
    here to PLATFORM_APPROVED.
    """
    if refund.status != RefundStatus.REQUESTED:
        raise ValidationFailedError("Only a requested refund can be moved to review.")

    refund.status = RefundStatus.UNDER_REVIEW
    refund.reviewed_by = reviewed_by
    refund.save(update_fields=["status", "reviewed_by", "updated_at"])
    return refund


def start_return(*, refund):
    """UNDER_REVIEW -> RETURN_IN_PROGRESS. Only for items that actually need to come back."""
    if refund.status != RefundStatus.UNDER_REVIEW:
        raise ValidationFailedError("Only a refund under review can start a return.")
    if not refund.requires_physical_return:
        raise ValidationFailedError("This item doesn't require a physical return.")

    refund.status = RefundStatus.RETURN_IN_PROGRESS
    refund.save(update_fields=["status", "updated_at"])
    return refund


def mark_item_received(*, refund, seller_user):
    """
    RETURN_IN_PROGRESS -> ITEM_RECEIVED. Seller action (spec section 26)
    - confirms the returned item has physically arrived. Scoped to the
    seller who actually owns this line item.
    """
    _require_seller_owns_item(refund, seller_user)
    if refund.status != RefundStatus.RETURN_IN_PROGRESS:
        raise ValidationFailedError("This refund isn't awaiting a return.")

    refund.status = RefundStatus.ITEM_RECEIVED
    refund.item_received_at = timezone.now()
    refund.save(update_fields=["status", "item_received_at", "updated_at"])
    return refund


def confirm_item_condition(*, refund, seller_user, notes):
    """
    ITEM_RECEIVED -> SELLER_CONDITION_CONFIRMED. Seller action (spec
    section 26) - records the seller's account of the item's condition.
    This is input to the platform's decision, NOT a decision itself:
    the seller cannot approve or execute the refund from here.
    """
    _require_seller_owns_item(refund, seller_user)
    if refund.status != RefundStatus.ITEM_RECEIVED:
        raise ValidationFailedError("This refund isn't awaiting a condition confirmation.")

    refund.status = RefundStatus.SELLER_CONDITION_CONFIRMED
    refund.seller_condition_notes = notes
    refund.seller_condition_confirmed_at = timezone.now()
    refund.save(update_fields=[
        "status", "seller_condition_notes", "seller_condition_confirmed_at", "updated_at",
    ])
    return refund


def reject_refund(*, refund, reviewed_by, reason=""):
    if refund.status not in _PRE_APPROVAL_STATUSES:
        raise ValidationFailedError("This refund is already past the point where it can be rejected.")

    refund.status = RefundStatus.REJECTED
    refund.reviewed_by = reviewed_by
    if reason:
        refund.admin_notes = reason
    refund.save(update_fields=["status", "reviewed_by", "admin_notes", "updated_at"])
    return refund


def approve_refund(*, refund, reviewed_by):
    """
    -> PLATFORM_APPROVED (admin/platform action only - spec section 26:
    "the seller must not directly execute the refund"). This used to
    call Paystack immediately; it no longer does. It only starts the
    mandatory delay - see begin_refund_processing for the actual call.
    """
    valid_from = (
        RefundStatus.SELLER_CONDITION_CONFIRMED if refund.requires_physical_return
        else RefundStatus.UNDER_REVIEW
    )
    if refund.status != valid_from:
        raise ValidationFailedError(f"This refund isn't ready for approval (expected {valid_from.label}).")

    refund.status = RefundStatus.PLATFORM_APPROVED
    refund.reviewed_by = reviewed_by
    refund.approved_at = timezone.now()
    refund.save(update_fields=["status", "reviewed_by", "approved_at", "updated_at"])
    return refund


@transaction.atomic
def begin_refund_processing(*, refund):
    """
    PLATFORM_APPROVED -> PROCESSING. This is the actual Paystack refund
    call. Spec section 27: "the frontend timer must never determine
    whether the refund can execute" - enforced right here, server-side,
    against refund.approved_at. No amount of frontend countdown
    manipulation can make this fire before the real delay has elapsed.
    """
    from apps.payments.services import PaystackRefundError, initiate_paystack_refund

    if refund.status != RefundStatus.PLATFORM_APPROVED:
        raise ValidationFailedError("Only an approved refund can begin processing.")

    elapsed = timezone.now() - refund.approved_at
    if elapsed.total_seconds() < REFUND_PROCESSING_DELAY_MINUTES * 60:
        remaining = REFUND_PROCESSING_DELAY_MINUTES * 60 - elapsed.total_seconds()
        raise ValidationFailedError(
            f"The required verification period hasn't elapsed yet ({int(remaining // 60)}m remaining)."
        )

    payment = refund.order_item.order.payments.filter(status="success").order_by("-created_at").first()
    if payment is None:
        raise ValidationFailedError("No successful payment found for this order.")

    refund.status = RefundStatus.PROCESSING

    try:
        response = initiate_paystack_refund(transaction_reference=payment.reference, amount=refund.amount)
    except PaystackRefundError as e:
        refund.status = RefundStatus.FAILED
        refund.admin_notes = str(e)
        refund.save(update_fields=["status", "admin_notes", "updated_at"])
        raise

    refund.provider_reference = str(response.get("reference") or response.get("id") or "")
    refund.save(update_fields=["status", "provider_reference", "updated_at"])

    if response.get("status") == "processed":
        mark_refund_processed(refund=refund)

    return refund


@transaction.atomic
def mark_refund_processed(*, refund):
    """PROCESSING -> PROCESSED ("Refunded"). Reverses the ledger/earning/commission for this line item (idempotent)."""
    reverse_order_item_financials(order_item=refund.order_item, reason=f"Refund {refund.pk} processed.")
    refund.status = RefundStatus.PROCESSED
    refund.processed_at = timezone.now()
    refund.save(update_fields=["status", "processed_at", "updated_at"])
    return refund


def mark_refund_failed(*, refund, reason=""):
    """PROCESSING -> FAILED. No ledger reversal happened yet, so there's nothing to undo."""
    refund.status = RefundStatus.FAILED
    if reason:
        refund.admin_notes = reason
    refund.save(update_fields=["status", "admin_notes", "updated_at"])
    return refund


def _require_seller_owns_item(refund, seller_user):
    if refund.order_item.seller_id is None or refund.order_item.seller.user_id != seller_user.id:
        raise ValidationFailedError("This isn't your item to act on.")

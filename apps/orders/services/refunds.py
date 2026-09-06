"""
Customer refund requests, admin approval, and the actual money-back-to-
customer step via Paystack - wired into the Phase 8 ledger reversal
machinery (apps.ledger.services.reverse_order_item_financials).
"""

from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import ValidationFailedError
from apps.ledger.services import reverse_order_item_financials

from ..models import Refund, RefundStatus


def request_refund(*, order_item, user, reason):
    """One active request per item at a time - a rejected one can be re-filed, an in-flight/succeeded one can't."""
    if order_item.order.user_id != user.id:
        raise ValidationFailedError("This isn't your order.")

    if not order_item.order.is_paid:
        raise ValidationFailedError("This order hasn't been paid for, so there's nothing to refund.")

    if Refund.objects.filter(
        order_item=order_item,
        status__in=[RefundStatus.REQUESTED, RefundStatus.PROCESSING, RefundStatus.PROCESSED],
    ).exists():
        raise ValidationFailedError("A refund has already been requested for this item.")

    return Refund.objects.create(
        order_item=order_item,
        requested_by=user,
        reason=reason,
        amount=order_item.subtotal,
        status=RefundStatus.REQUESTED,
    )


def reject_refund(*, refund, reviewed_by, reason=""):
    refund.status = RefundStatus.REJECTED
    refund.reviewed_by = reviewed_by
    if reason:
        refund.admin_notes = reason
    refund.save(update_fields=["status", "reviewed_by", "admin_notes", "updated_at"])
    return refund


@transaction.atomic
def approve_refund(*, refund, reviewed_by):
    """
    The approval IS the trigger - calls Paystack's refund API against
    the order's successful payment. If Paystack's response already says
    "processed", the ledger is reversed right away; otherwise the
    refund sits in PROCESSING until the refund.processed/refund.failed
    webhook resolves it (apps.payments.views.paystack_webhook) - the
    ledger is never reversed on the strength of the API call alone.
    """
    from apps.payments.services import PaystackRefundError, initiate_paystack_refund

    if refund.status != RefundStatus.REQUESTED:
        raise ValidationFailedError("Only requested refunds can be approved.")

    payment = refund.order_item.order.payments.filter(status="success").order_by("-created_at").first()
    if payment is None:
        raise ValidationFailedError("No successful payment found for this order.")

    refund.reviewed_by = reviewed_by
    refund.status = RefundStatus.PROCESSING

    try:
        response = initiate_paystack_refund(transaction_reference=payment.reference, amount=refund.amount)
    except PaystackRefundError as e:
        refund.status = RefundStatus.FAILED
        refund.admin_notes = str(e)
        refund.save(update_fields=["status", "reviewed_by", "admin_notes", "updated_at"])
        raise

    refund.provider_reference = str(response.get("reference") or response.get("id") or "")
    refund.save(update_fields=["status", "reviewed_by", "provider_reference", "updated_at"])

    if response.get("status") == "processed":
        mark_refund_processed(refund=refund)

    return refund


@transaction.atomic
def mark_refund_processed(*, refund):
    """PROCESSING -> PROCESSED. Reverses the ledger/earning/commission for this line item (idempotent)."""
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
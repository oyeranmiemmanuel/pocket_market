"""
Business logic for rider onboarding. Mirrors apps.sellers.services /
apps.affiliates.services - status transitions live here, never as a
direct .status = ... edit in a view or in Django admin (spec section 42).
"""

from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import ValidationFailedError

from .models import RiderEarning, RiderEarningStatus, RiderProfile, RiderStatus


def apply_for_rider(*, user, full_name, phone, contact_email, service_area, vehicle_type):
    """
    Create a pending rider application. One per user - raises if they
    already have a profile (regardless of its current status), same rule
    as apply_for_seller/apply_for_affiliate: a rejected/suspended rider
    re-applies by going through re-review of the existing profile, not by
    spamming new ones.
    """
    if RiderProfile.objects.filter(user=user).exists():
        raise ValidationFailedError("You already have a rider application on file.")

    profile = RiderProfile.objects.create(
        user=user,
        full_name=full_name,
        phone=phone,
        contact_email=contact_email,
        service_area=service_area,
        vehicle_type=vehicle_type,
        status=RiderStatus.PENDING,
    )
    return profile


def approve_rider(*, profile, reviewed_by):
    profile.status = RiderStatus.APPROVED
    profile.reviewed_at = timezone.now()
    profile.reviewed_by = reviewed_by
    profile.rejection_reason = ""
    profile.save(update_fields=["status", "reviewed_at", "reviewed_by", "rejection_reason"])
    return profile


def reject_rider(*, profile, reviewed_by, reason=""):
    profile.status = RiderStatus.REJECTED
    profile.reviewed_at = timezone.now()
    profile.reviewed_by = reviewed_by
    profile.rejection_reason = reason
    profile.save(update_fields=["status", "reviewed_at", "reviewed_by", "rejection_reason"])
    return profile


def suspend_rider(*, profile, reviewed_by, reason=""):
    profile.status = RiderStatus.SUSPENDED
    profile.is_available = False
    profile.reviewed_at = timezone.now()
    profile.reviewed_by = reviewed_by
    profile.rejection_reason = reason
    profile.save(update_fields=["status", "is_available", "reviewed_at", "reviewed_by", "rejection_reason"])
    return profile


def reactivate_rider(*, profile, reviewed_by):
    """Back to APPROVED from SUSPENDED or INACTIVE."""
    if profile.status not in (RiderStatus.SUSPENDED, RiderStatus.INACTIVE):
        raise ValidationFailedError(f"Cannot reactivate a rider from status '{profile.status}'.")

    profile.status = RiderStatus.APPROVED
    profile.reviewed_at = timezone.now()
    profile.reviewed_by = reviewed_by
    profile.save(update_fields=["status", "reviewed_at", "reviewed_by"])
    return profile


def verify_rider(*, profile, reviewed_by):
    """
    Separate from approval (spec section 5's "Verification status" is its
    own field) - e.g. an admin confirming ID/license documents.
    """
    profile.verified = True
    profile.reviewed_at = timezone.now()
    profile.reviewed_by = reviewed_by
    profile.save(update_fields=["verified", "reviewed_at", "reviewed_by"])
    return profile


def deactivate_rider(*, profile):
    """Rider-initiated pause (APPROVED -> INACTIVE), not an admin action."""
    if profile.status != RiderStatus.APPROVED:
        raise ValidationFailedError("Only an approved rider can deactivate themselves.")

    profile.status = RiderStatus.INACTIVE
    profile.is_available = False
    profile.save(update_fields=["status", "is_available"])
    return profile


def set_rider_availability(*, profile, available: bool):
    """
    Rider-controlled "on shift" toggle. Only meaningful, and only
    allowed, while the account is APPROVED - never lets a suspended or
    still-pending rider flip themselves available.
    """
    if profile.status != RiderStatus.APPROVED:
        raise ValidationFailedError("Only an approved rider can set availability.")

    profile.is_available = available
    profile.save(update_fields=["is_available"])
    return profile


# ---------------------------------------------------------------------------
# Spec sections 16/22/24 - rider earnings. Mirrors apps.sellers.services'
# record_seller_earning/confirm_seller_earning/mark_seller_earning_available
# and apps.affiliates.services' equivalents exactly, one leg (pickup or
# delivery) at a time instead of one order_item at a time.
# ---------------------------------------------------------------------------

def record_rider_earning(*, rider, order, amount, pickup_task=None, delivery_task=None):
    """
    Called once, at the moment a leg is actually completed -
    apps.logistics.services.mark_package_collected for a pickup_task, or
    mark_delivery_task_delivered for a delivery_task. Exactly one of the
    two must be given (enforced at the DB level too, see RiderEarning's
    CheckConstraint) - idempotent via the same-model unique constraints,
    so a retried call for the same task is a no-op rather than a double
    credit.
    """
    if bool(pickup_task) == bool(delivery_task):
        raise ValidationFailedError("Exactly one of pickup_task or delivery_task must be given.")

    existing = RiderEarning.objects.filter(
        pickup_task=pickup_task, delivery_task=delivery_task, reversal_of__isnull=True,
    ).first()
    if existing is not None:
        return existing

    return RiderEarning.objects.create(
        rider=rider, order=order, amount=amount,
        pickup_task=pickup_task, delivery_task=delivery_task,
        status=RiderEarningStatus.PENDING,
    )


def confirm_rider_earning(*, earning):
    """PENDING -> CONFIRMED ("Held"). Manual admin step for now (no automatic timer), mirroring confirm_seller_earning."""
    earning.status = RiderEarningStatus.CONFIRMED
    earning.confirmed_at = timezone.now()
    earning.save(update_fields=["status", "confirmed_at", "updated_at"])
    return earning


def mark_rider_earning_available(*, earning):
    """CONFIRMED -> AVAILABLE, i.e. cleared for payout."""
    earning.status = RiderEarningStatus.AVAILABLE
    earning.save(update_fields=["status", "updated_at"])
    return earning


def mark_rider_earning_paid(*, earning):
    """AVAILABLE -> PAID ("Withdrawn"). No RiderPayout batching model exists yet - a direct admin action for now."""
    earning.status = RiderEarningStatus.PAID
    earning.save(update_fields=["status", "updated_at"])
    return earning


def cancel_rider_earning(*, earning, reason=""):
    earning.status = RiderEarningStatus.CANCELLED
    earning.save(update_fields=["status", "updated_at"])
    return earning


@transaction.atomic
def reverse_rider_earning(*, earning, reason=""):
    """
    Mirrors apps.sellers.services.reverse_seller_earning: the original
    row is never deleted or silently edited - a second row is created
    with `reversal_of` pointing back at it, and the original flips to
    REVERSED. Called when a refund on this order needs to claw back
    what a rider was credited for handling it.
    """
    if earning.reversal_of_id is not None:
        raise ValidationFailedError("Cannot reverse a reversal row.")
    if earning.status == RiderEarningStatus.REVERSED:
        return earning.reversals.first()  # already reversed - idempotent

    reversal = RiderEarning.objects.create(
        rider=earning.rider,
        order=earning.order,
        pickup_task=earning.pickup_task,
        delivery_task=earning.delivery_task,
        amount=-earning.amount,
        status=RiderEarningStatus.REVERSED,
        reversal_of=earning,
    )
    earning.status = RiderEarningStatus.REVERSED
    earning.save(update_fields=["status", "updated_at"])
    return reversal
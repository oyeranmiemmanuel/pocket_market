"""
Business logic for rider onboarding. Mirrors apps.sellers.services /
apps.affiliates.services - status transitions live here, never as a
direct .status = ... edit in a view or in Django admin (spec section 42).
"""

from django.utils import timezone

from apps.core.exceptions import ValidationFailedError

from .models import RiderProfile, RiderStatus


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
"""
KYC lifecycle services (Phase 1 - collection & confirmation only).

Every status transition goes through here, never a direct
`.status = ...` edit in a view or in Django admin - same rule
apps.sellers/riders/affiliates.services already follow - so every
change is consistently audit-logged.
"""

from django.db import transaction
from django.utils import timezone

from apps.core.enums import KYCStatus
from apps.core.exceptions import ValidationFailedError

from .models import AffiliateKYC, BuyerKYC, KYCAuditLog, RiderKYC, SellerKYC

# ---------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------

def log_kyc_action(*, kyc_subject, actor, action, from_status="", to_status="", notes=""):
    return KYCAuditLog.objects.create(
        kyc_subject=kyc_subject,
        actor=actor,
        action=action,
        from_status=from_status,
        to_status=to_status,
        notes=notes,
    )


def log_kyc_access(*, kyc_subject, actor, notes=""):
    """
    Call this whenever a sensitive field (ID number, licence number,
    document file) is deliberately viewed in full - e.g. from an admin
    detail view - not just listed in masked form.
    """
    return log_kyc_action(kyc_subject=kyc_subject, actor=actor, action=KYCAuditLog.Action.ACCESSED, notes=notes)


# ---------------------------------------------------------------------
# Generic transitions - shared by all four subject types
# ---------------------------------------------------------------------

def _submit(*, instance, actor, fields):
    if instance.status not in (KYCStatus.NOT_SUBMITTED, KYCStatus.RESUBMISSION, KYCStatus.REJECTED):
        raise ValidationFailedError(f"Cannot submit KYC from status '{instance.get_status_display()}'.")

    from_status = instance.status
    for field, value in fields.items():
        setattr(instance, field, value)

    instance.status = KYCStatus.SUBMITTED
    instance.submitted_at = timezone.now()
    instance.rejection_reason = ""
    instance.save()

    log_kyc_action(
        kyc_subject=instance, actor=actor, action=KYCAuditLog.Action.SUBMITTED,
        from_status=from_status, to_status=KYCStatus.SUBMITTED,
    )
    return instance


def move_under_review(*, instance, actor):
    if instance.status != KYCStatus.SUBMITTED:
        raise ValidationFailedError("Only a submitted KYC record can be moved under review.")

    from_status = instance.status
    instance.status = KYCStatus.UNDER_REVIEW
    instance.save(update_fields=["status", "updated_at"])

    log_kyc_action(
        kyc_subject=instance, actor=actor, action=KYCAuditLog.Action.UNDER_REVIEW,
        from_status=from_status, to_status=KYCStatus.UNDER_REVIEW,
    )
    return instance


def confirm_kyc(*, instance, reviewed_by):
    if instance.status not in (KYCStatus.SUBMITTED, KYCStatus.UNDER_REVIEW):
        raise ValidationFailedError(f"Cannot confirm KYC from status '{instance.get_status_display()}'.")

    from_status = instance.status
    instance.status = KYCStatus.CONFIRMED
    instance.reviewed_at = timezone.now()
    instance.reviewed_by = reviewed_by
    instance.rejection_reason = ""
    instance.save()

    log_kyc_action(
        kyc_subject=instance, actor=reviewed_by, action=KYCAuditLog.Action.CONFIRMED,
        from_status=from_status, to_status=KYCStatus.CONFIRMED,
    )

    # RiderProfile.verified pre-dates this app and was always meant to
    # mean "identity/licence checked" - this is the one deliberate link
    # between KYC confirmation and existing marketplace state.
    if isinstance(instance, RiderKYC) and not instance.rider.verified:
        instance.rider.verified = True
        instance.rider.save(update_fields=["verified"])

    return instance


def reject_kyc(*, instance, reviewed_by, reason, allow_resubmission=True):
    if instance.status not in (KYCStatus.SUBMITTED, KYCStatus.UNDER_REVIEW):
        raise ValidationFailedError(f"Cannot reject KYC from status '{instance.get_status_display()}'.")

    from_status = instance.status
    instance.status = KYCStatus.RESUBMISSION if allow_resubmission else KYCStatus.REJECTED
    instance.reviewed_at = timezone.now()
    instance.reviewed_by = reviewed_by
    instance.rejection_reason = reason
    instance.save()

    log_kyc_action(
        kyc_subject=instance, actor=reviewed_by, action=KYCAuditLog.Action.REJECTED,
        from_status=from_status, to_status=instance.status, notes=reason,
    )
    return instance


# ---------------------------------------------------------------------
# Per-subject submission entry points
# ---------------------------------------------------------------------

@transaction.atomic
def submit_buyer_kyc(*, user, **fields):
    instance, _ = BuyerKYC.objects.get_or_create(user=user)
    return _submit(instance=instance, actor=user, fields=fields)


@transaction.atomic
def submit_seller_kyc(*, seller, **fields):
    instance, _ = SellerKYC.objects.get_or_create(seller=seller)
    return _submit(instance=instance, actor=seller.user, fields=fields)


@transaction.atomic
def submit_affiliate_kyc(*, affiliate, **fields):
    instance, _ = AffiliateKYC.objects.get_or_create(affiliate=affiliate)
    return _submit(instance=instance, actor=affiliate.user, fields=fields)


@transaction.atomic
def submit_rider_kyc(*, rider, **fields):
    instance, _ = RiderKYC.objects.get_or_create(rider=rider)
    return _submit(instance=instance, actor=rider.user, fields=fields)
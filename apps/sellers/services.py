"""
Seller application lifecycle + commission rate resolution.
"""

from decimal import Decimal

from django.utils import timezone

from apps.core.constants import PLATFORM_COMMISSION_RATE_DEFAULT
from apps.core.exceptions import ValidationFailedError
from apps.core.utils import unique_slugify

from .models import SellerProfile, SellerStatus


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

"""
Affiliate application lifecycle + (Phase 6) referral link generation and
click tracking. Commission rate resolution / conversion recording
deliberately NOT included here yet - that's Phase 7, once a sale can
actually be attributed to a click.
"""

from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.urls import Resolver404, resolve
from django.utils import timezone

from apps.core.constants import AFFILIATE_ATTRIBUTION_COOKIE_NAME, AFFILIATE_CLICK_DEDUP_MINUTES
from apps.core.exceptions import ValidationFailedError
from apps.core.utils import generate_reference

from .models import AffiliateClick, AffiliateLink, AffiliateProfile, AffiliateStatus

def _generate_unique_affiliate_code() -> str:
    """AFF-XXXXXXXXXX, regenerated on the rare collision."""
    for _ in range(5):
        code = generate_reference("AFF", length=8)
        if not AffiliateProfile.objects.filter(affiliate_code=code).exists():
            return code
    raise ValidationFailedError("Could not generate a unique affiliate code, try again.")


def apply_for_affiliate(*, user):
    """
    Create a pending affiliate application. One per user - raises if
    they already have a profile (regardless of its current status), so
    a rejected/suspended affiliate can't just spam new applications;
    that should go through re-review of the existing profile instead.
    """
    if AffiliateProfile.objects.filter(user=user).exists():
        raise ValidationFailedError("You already have an affiliate application on file.")

    profile = AffiliateProfile.objects.create(
        user=user,
        affiliate_code=_generate_unique_affiliate_code(),
        status=AffiliateStatus.PENDING,
    )
    return profile


def approve_affiliate(*, profile, reviewed_by):
    profile.status = AffiliateStatus.ACTIVE
    profile.reviewed_at = timezone.now()
    profile.reviewed_by = reviewed_by
    profile.rejection_reason = ""
    profile.save(update_fields=["status", "reviewed_at", "reviewed_by", "rejection_reason"])
    return profile


def reject_affiliate(*, profile, reviewed_by, reason=""):
    profile.status = AffiliateStatus.REJECTED
    profile.reviewed_at = timezone.now()
    profile.reviewed_by = reviewed_by
    profile.rejection_reason = reason
    profile.save(update_fields=["status", "reviewed_at", "reviewed_by", "rejection_reason"])
    return profile


def suspend_affiliate(*, profile, reviewed_by, reason=""):
    profile.status = AffiliateStatus.SUSPENDED
    profile.reviewed_at = timezone.now()
    profile.reviewed_by = reviewed_by
    profile.rejection_reason = reason
    profile.save(update_fields=["status", "reviewed_at", "reviewed_by", "rejection_reason"])
    return profile


# ---------------------------------------------------------------------------
# Phase 6 - referral tracking.
# ---------------------------------------------------------------------------

def generate_affiliate_link(*, affiliate, product):
    """
    Explicit "Generate Link" action from the affiliate's dashboard.
    Idempotent - calling it again for a product they've already
    generated a link for just returns (and reactivates, if needed) the
    existing one rather than erroring or creating a duplicate row.
    """
    link, _ = AffiliateLink.objects.get_or_create(
        affiliate=affiliate,
        product=product,
        defaults={"referral_code": affiliate.affiliate_code},
    )
    if not link.is_active:
        link.is_active = True
        link.save(update_fields=["is_active"])
    return link


def _resolve_product_from_path(path):
    """
    Figures out which product (if any) a request path refers to, using
    Django's own URL resolver rather than `request.resolver_match` -
    that attribute isn't reliably populated yet at the point middleware
    needs it, whereas resolve() works regardless of middleware ordering.
    """
    from apps.catalog.models import Product  # local import - avoids a catalog<->affiliates import cycle at app-load time

    try:
        match = resolve(path)
    except Resolver404:
        return None

    if match.view_name != "catalog:product_detail":
        return None

    return Product.active.filter(slug=match.kwargs.get("slug"), is_active=True).first()


def _is_duplicate_click(*, affiliate, product, session_key):
    cutoff = timezone.now() - timedelta(minutes=AFFILIATE_CLICK_DEDUP_MINUTES)
    return AffiliateClick.objects.filter(
        affiliate=affiliate,
        product=product,
        session_key=session_key,
        created_at__gte=cutoff,
    ).exists()


def record_referral_click(request, affiliate_code):
    """
    Called by AffiliateTrackingMiddleware whenever a request carries
    ?ref=<code>. Validates the code, guards against self-referral and
    obvious repeat-click spam, and (best-effort) logs an AffiliateClick.

    Returns the signed cookie value to attribute this visitor to the
    affiliate, or None if the code was invalid/inactive or this was a
    self-referral - in either case no cookie is set and the page just
    loads normally. A bad ?ref= should never break the page.
    """
    try:
        affiliate = AffiliateProfile.objects.get(
            affiliate_code=affiliate_code, status=AffiliateStatus.ACTIVE,
        )
    except AffiliateProfile.DoesNotExist:
        return None

    # Fraud prevention (spec section 43) - an affiliate can't refer
    # themselves for commission purposes, so don't even attribute or
    # log a click for their own visits.
    if request.user.is_authenticated:
        own_profile = getattr(request.user, "affiliate_profile", None)
        if own_profile is not None and own_profile.pk == affiliate.pk:
            return None

    product = _resolve_product_from_path(request.path)

    affiliate_link = None
    if product is not None:
        affiliate_link, _ = AffiliateLink.objects.get_or_create(
            affiliate=affiliate,
            product=product,
            defaults={"referral_code": affiliate.affiliate_code},
        )

    # Best-effort session key, purely for click de-duplication - never
    # used to identify a person. Forces a session row to exist if this
    # is a brand-new anonymous visitor.
    if not request.session.session_key:
        request.session.save()
    session_key = request.session.session_key or ""

    if not _is_duplicate_click(affiliate=affiliate, product=product, session_key=session_key):
        AffiliateClick.objects.create(
            affiliate=affiliate,
            affiliate_link=affiliate_link,
            product=product,
            session_key=session_key,
        )

    return signing.dumps(affiliate_code)


def get_attributed_affiliate(request):
    """
    Reads the attribution cookie set by AffiliateTrackingMiddleware.
    Returns the currently-attributed AffiliateProfile, or None if there
    isn't one, it's tampered with, or that affiliate is no longer
    active. Nothing in this phase calls this yet - it's here for Phase 7
    (commission calculation at checkout) to consume.
    """
    raw = request.COOKIES.get(AFFILIATE_ATTRIBUTION_COOKIE_NAME)
    if not raw:
        return None

    try:
        affiliate_code = signing.loads(raw)
    except signing.BadSignature:
        return None

    return AffiliateProfile.objects.filter(
        affiliate_code=affiliate_code, status=AffiliateStatus.ACTIVE,
    ).first()
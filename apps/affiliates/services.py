"""
Affiliate application lifecycle, (Phase 6) referral link generation and
click tracking, and (Phase 7) commission rate resolution + conversion
recording once a sale can be attributed to a click.
"""

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core import signing
from django.db import transaction
from django.urls import Resolver404, resolve
from django.utils import timezone

from apps.core.constants import (
    AFFILIATE_ATTRIBUTION_COOKIE_NAME,
    AFFILIATE_CLICK_DEDUP_MINUTES,
    PLATFORM_AFFILIATE_COMMISSION_RATE_DEFAULT,
)
from apps.core.exceptions import ValidationFailedError

from apps.core.utils import generate_reference

from .models import (
    AffiliateClick,
    AffiliateCommission,
    AffiliateLink,
    AffiliateProfile,
    AffiliateStatus,
    CommissionStatus,
)

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


# ---------------------------------------------------------------------------
# Phase 7 - commission calculation.
#
# Mirrors apps.sellers.services.resolve_commission_rate's hierarchy
# pattern, but for what an AFFILIATE earns rather than what the PLATFORM
# takes. Two different fields on the same models (Product.commission_rate
# vs Product.affiliate_commission_rate, SellerProfile.commission_rate vs
# SellerProfile.affiliate_commission_rate), so the two calculations never
# get tangled together.
# ---------------------------------------------------------------------------

def resolve_affiliate_commission_rate(*, product, affiliate) -> Decimal:
    """
    Spec section 16's hierarchy (product -> seller -> global), with one
    addition on top: an affiliate's own AffiliateProfile.commission_rate,
    when set, is treated as a negotiated rate for that affiliate and wins
    over all three - it exists specifically so an individual affiliate can
    be given a custom deal (spec section 9 already defines the field for
    exactly this). See docs/28_DECISIONS.md.

        1. AffiliateProfile.commission_rate  (this affiliate's own rate)
        2. Product.affiliate_commission_rate (this product's rate)
        3. SellerProfile.affiliate_commission_rate (this seller's rate)
        4. PLATFORM_AFFILIATE_COMMISSION_RATE_DEFAULT (global fallback)
    """
    if affiliate.commission_rate is not None:
        return affiliate.commission_rate

    if product.affiliate_commission_rate is not None:
        return product.affiliate_commission_rate

    if product.seller_id is not None and product.seller.affiliate_commission_rate is not None:
        return product.seller.affiliate_commission_rate

    return Decimal(PLATFORM_AFFILIATE_COMMISSION_RATE_DEFAULT)


def calculate_order_item_allocation(*, order_item, affiliate=None):
    """
    Pure calculation, no database writes - the "dedicated service/function
    for calculating order financial allocations" spec section 17 asks for.
    Never called from a template or with client-supplied numbers; always
    from OrderItem.unit_price/quantity and the snapshotted/resolved rates.

    Returns a dict of Decimals that always satisfy:

        platform_amount + affiliate_amount + seller_amount == gross

    i.e. the affiliate's cut comes out of the seller's share, not the
    platform's - matching spec section 17's worked example exactly
    (₦50,000 product, 10% platform, 5% affiliate -> platform ₦5,000,
    affiliate ₦2,500, seller ₦42,500). Platform-owned products (no
    seller, platform_commission_rate=100) simply leave nothing for an
    affiliate to be paid from what would be the seller's share; the
    hierarchy in resolve_affiliate_commission_rate never depends on a
    seller existing, so affiliate referrals of platform products still
    work if the platform allows it - the platform's own amount is what
    absorbs the affiliate cost when there's no seller instead.
    """
    gross = order_item.subtotal
    platform_rate = order_item.platform_commission_rate or Decimal("0")
    platform_amount = (gross * platform_rate / 100).quantize(order_item.unit_price)

    affiliate_rate = Decimal("0")
    affiliate_amount = Decimal("0.00")
    if affiliate is not None and order_item.product_id is not None:
        affiliate_rate = resolve_affiliate_commission_rate(
            product=order_item.product, affiliate=affiliate,
        )
        affiliate_amount = (gross * affiliate_rate / 100).quantize(order_item.unit_price)

    if order_item.seller_id is not None:
        seller_amount = gross - platform_amount - affiliate_amount
    else:
        # Platform-owned line item - there's no seller to net anything;
        # the platform absorbs the affiliate cost out of its own 100%
        # share instead of manufacturing a seller_amount that belongs to
        # nobody.
        seller_amount = Decimal("0.00")
        platform_amount = gross - affiliate_amount

    return {
        "gross": gross,
        "platform_commission_rate": platform_rate,
        "platform_amount": platform_amount,
        "affiliate_commission_rate": affiliate_rate,
        "affiliate_amount": affiliate_amount,
        "seller_amount": seller_amount,
    }


def _mark_matching_click_converted(*, affiliate, product):
    """
    Best-effort only - AffiliateClick doesn't carry a reference back to
    the order it eventually led to (clicks happen long before checkout,
    possibly across several browsing sessions), so this just flips the
    most recent not-yet-converted click for this affiliate+product. Purely
    informational for admin/affiliate-facing click-vs-conversion stats;
    nothing financial depends on it.
    """
    click = (
        AffiliateClick.objects.filter(affiliate=affiliate, product=product, converted=False)
        .order_by("-created_at")
        .first()
    )
    if click is not None:
        click.converted = True
        click.save(update_fields=["converted"])


def resolve_effective_affiliate(order):
    """
    Returns the AffiliateProfile that should be credited for this order's
    commissions/ledger entries, or None if there isn't an eligible one.

    Centralizes the eligibility rules (spec section 43 - fraud
    prevention) in one place so anything that needs to know "does this
    order have a payable affiliate" agrees with record_conversion_for_order
    below - both it and apps.ledger.services.process_order_financials
    (Phase 8) call this rather than each re-deriving the rules, which
    would risk the affiliate commission and the seller's net earnings
    silently disagreeing about whether an affiliate was involved.

    No-ops (returns None) if:
    - the order has no attributed affiliate, or
    - that affiliate is no longer ACTIVE (may have been suspended between
      the click and this payment - re-checked here, not just at click
      time), or
    - the affiliate is the same person as the order's customer
      (self-referral - spec section 43; the click-tracking layer already
      guards this too, this is defense in depth against attribution
      surviving a login/account-switch).
    """
    affiliate = order.affiliate
    if affiliate is None:
        return None

    if affiliate.status != AffiliateStatus.ACTIVE:
        return None

    if order.user_id is not None and getattr(affiliate, "user_id", None) == order.user_id:
        return None

    return affiliate


@transaction.atomic
def record_conversion_for_order(order):
    """
    Called once, from apps.ledger.services.process_order_financials (which
    is itself called from apps.payments.services._finalize_successful_payment
    right after an order is marked paid). Creates one AffiliateCommission
    per eligible OrderItem for whichever affiliate resolve_effective_affiliate
    says should be credited.

    Safe to call more than once for the same order (idempotent): the
    UniqueConstraint on AffiliateCommission(order_item, reversal_of=NULL)
    means a repeat call just skips items that already have a commission,
    rather than erroring or double-crediting the affiliate (spec section
    39). Runs inside the same atomic block as the rest of payment
    finalization, so a failure here rolls back payment finalization too -
    never leaves "order paid" without its commissions (spec section 38).
    """
    affiliate = resolve_effective_affiliate(order)
    if affiliate is None:
        return []

    existing_item_ids = set(
        AffiliateCommission.objects.filter(
            order=order, reversal_of__isnull=True,
        ).values_list("order_item_id", flat=True)
    )

    created = []
    for item in order.items.select_related("product", "seller").all():
        if item.pk in existing_item_ids or item.product_id is None:
            continue

        allocation = calculate_order_item_allocation(order_item=item, affiliate=affiliate)
        if allocation["affiliate_amount"] <= 0:
            continue

        affiliate_link = AffiliateLink.objects.filter(
            affiliate=affiliate, product=item.product,
        ).first()

        commission = AffiliateCommission.objects.create(
            affiliate=affiliate,
            order=order,
            order_item=item,
            affiliate_link=affiliate_link,
            order_amount=allocation["gross"],
            commission_rate=allocation["affiliate_commission_rate"],
            commission_amount=allocation["affiliate_amount"],
            status=CommissionStatus.PENDING,
        )
        created.append(commission)

        _mark_matching_click_converted(affiliate=affiliate, product=item.product)

    return created

def confirm_commission(*, commission):
    """PENDING -> CONFIRMED. Manual admin step for now (no automatic timer)."""
    commission.status = CommissionStatus.CONFIRMED
    commission.save(update_fields=["status", "updated_at"])
    return commission


def mark_commission_available(*, commission):
    """CONFIRMED -> AVAILABLE, i.e. cleared for payout (consumed by Phase 9)."""
    commission.status = CommissionStatus.AVAILABLE
    commission.save(update_fields=["status", "updated_at"])
    return commission


def cancel_commission(*, commission, reason=""):
    """Any pre-PAID status -> CANCELLED - used when a commission should never have existed (e.g. fraud found after the fact)."""
    commission.status = CommissionStatus.CANCELLED
    if reason:
        commission.notes = reason
    commission.save(update_fields=["status", "notes", "updated_at"])
    return commission


@transaction.atomic
def reverse_commission(*, commission, reason=""):
    """
    Spec section 25 - a refund on an already CONFIRMED/AVAILABLE/PAID
    commission doesn't delete or silently edit it; it creates a second,
    negative-of-the-original row (`reversal_of` pointing back) and flips
    the original to REVERSED, so both the original grant and its reversal
    stay visible in the affiliate's history. No refund flow exists yet in
    this codebase to call this automatically (see docs/28_DECISIONS.md) -
    it's here ready for whenever refunds are built.
    """
    if commission.status == CommissionStatus.REVERSED:
        return commission  # already reversed - idempotent

    reversal = AffiliateCommission.objects.create(
        affiliate=commission.affiliate,
        order=commission.order,
        order_item=commission.order_item,
        affiliate_link=commission.affiliate_link,
        order_amount=commission.order_amount,
        commission_rate=commission.commission_rate,
        commission_amount=-commission.commission_amount,
        status=CommissionStatus.REVERSED,
        reversal_of=commission,
        notes=reason,
    )

    commission.status = CommissionStatus.REVERSED
    commission.save(update_fields=["status", "updated_at"])

    return reversal
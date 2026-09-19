"""
Global project constants.
"""

from decimal import Decimal

DEFAULT_CURRENCY = "NGN"

DEFAULT_COUNTRY = "Nigeria"

DEFAULT_LANGUAGE = "en"

DEFAULT_PAGE_SIZE = 20

MAX_PAGE_SIZE = 100

PHONE_NUMBER_LENGTH = 11

MAX_IMAGE_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB
# Flat fees in Naira - not carrier/distance-calculated yet. Local
# delivery priced lower than shipping to reinforce it as the
# faster/closer option alongside its shorter tracking pipeline.
LOCAL_DELIVERY_FEE = 1000
SHIPPING_FEE = 2500

# Bottom of the commission resolution hierarchy: Product.commission_rate
# -> SellerProfile.commission_rate -> this. Percentage the platform
# takes from a seller's sale.
PLATFORM_COMMISSION_RATE_DEFAULT = 10  # percent

# Bottom of the affiliate commission hierarchy: same idea, for affiliate
# payouts on referred sales.
PLATFORM_AFFILIATE_COMMISSION_RATE_DEFAULT = 5  # percent

# Seller-facing bounds (Marketplace Frontend Roadmap, section 6): a
# seller may only ever set Product.affiliate_commission_rate somewhere in
# this window. Enforced in three places - HTML min/max + JS clamp on the
# seller product form (UX only), Product.affiliate_commission_rate's
# validators (apps.catalog.models), and SellerProductForm.clean_affiliate_commission_rate
# - so the range can never be bypassed just by disabling JS or posting a
# raw form.
AFFILIATE_COMMISSION_RATE_MIN = 5    # percent
AFFILIATE_COMMISSION_RATE_MAX = 80   # percent

# Pre-filled starting point for the commission slider when a seller is
# creating a brand new product (their first product has no prior rate to
# default to). Purely a UX nicety - has no bearing on validation.
AFFILIATE_COMMISSION_RATE_SUGGESTED_DEFAULT = 20  # percent


# Name of the signed cookie AffiliateTrackingMiddleware sets when a
# visitor arrives via ?ref=<affiliate_code>. Its lifetime is
# settings.AFFILIATE_ATTRIBUTION_WINDOW_DAYS, not hard-coded here.
AFFILIATE_ATTRIBUTION_COOKIE_NAME = "aff_ref"

# How long a de-duplicated click "counts" as the same visit for the same
# affiliate+product - prevents a page refresh or repeat visit within this
# window from inflating the click count. Not the same as the attribution
# window (that's settings.AFFILIATE_ATTRIBUTION_WINDOW_DAYS).
AFFILIATE_CLICK_DEDUP_MINUTES = 30

# How long is a buyer's protection window after delivery, so refund/
# dispute requests are still simple/fast-tracked (spec section 21). This
# is display/informational only where it's shown - actual payout release
# is a separate, currently-manual admin action (apps.sellers.services.
# mark_seller_earning_available), not driven by this constant.
BUYER_PROTECTION_WINDOW_HOURS = 48

# Spec section 23 - deliberately different from BUYER_PROTECTION_WINDOW_HOURS:
# an affiliate's commission is held longer than the buyer's own refund
# window, since a refund can still be filed for a short while after that
# window nominally closes (admin discretion) and shouldn't be able to
# claw back a commission that's already been paid out.
AFFILIATE_COMMISSION_HOLD_HOURS = 50

# Spec section 27 - mandatory pause between an admin approving a refund
# and the actual Paystack refund call firing. Enforced server-side in
# apps.orders.services.refunds.begin_refund_processing - a frontend
# countdown is informational only and can't make this fire early.
REFUND_PROCESSING_DELAY_MINUTES = 15

# Spec sections 16/24 - of a seller's per-order delivery fee, how much
# goes to whoever collects the package (pickup leg) vs whoever completes
# final delivery (delivery leg). A placeholder split ratio - there's no
# real distance/effort-based rider pricing model yet. Must sum to 1.
RIDER_PICKUP_EARNING_SHARE = Decimal("0.40")
RIDER_DELIVERY_EARNING_SHARE = Decimal("0.60")
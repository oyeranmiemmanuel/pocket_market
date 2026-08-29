"""
Global project constants.
"""

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


# Name of the signed cookie AffiliateTrackingMiddleware sets when a
# visitor arrives via ?ref=<affiliate_code>. Its lifetime is
# settings.AFFILIATE_ATTRIBUTION_WINDOW_DAYS, not hard-coded here.
AFFILIATE_ATTRIBUTION_COOKIE_NAME = "aff_ref"

# How long a de-duplicated click "counts" as the same visit for the same
# affiliate+product - prevents a page refresh or repeat visit within this
# window from inflating the click count. Not the same as the attribution
# window (that's settings.AFFILIATE_ATTRIBUTION_WINDOW_DAYS).
AFFILIATE_CLICK_DEDUP_MINUTES = 30
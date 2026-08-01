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

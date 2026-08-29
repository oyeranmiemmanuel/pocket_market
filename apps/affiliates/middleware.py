"""
AffiliateTrackingMiddleware - Phase 6.

Registered in config/settings.py's MIDDLEWARE list. On every request
that carries ?ref=<code>, calls the existing record_referral_click()
service (validation, fraud guard, click logging all already live in
services.py) and, if it returns a signed value, sets/refreshes the
attribution cookie on the OUTGOING response for
settings.AFFILIATE_ATTRIBUTION_WINDOW_DAYS.

A missing/invalid ?ref= must never break the page - this middleware
only ever adds a cookie, it never redirects or raises.
"""

from django.conf import settings

from apps.core.constants import AFFILIATE_ATTRIBUTION_COOKIE_NAME

from .services import record_referral_click


class AffiliateTrackingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        affiliate_code = request.GET.get("ref")

        signed_value = None
        if affiliate_code:
            # Best-effort: any unexpected failure here (bad code, DB
            # hiccup, etc.) must not take the whole page down with it.
            try:
                signed_value = record_referral_click(request, affiliate_code)
            except Exception:
                signed_value = None

        response = self.get_response(request)

        if signed_value:
            response.set_cookie(
                AFFILIATE_ATTRIBUTION_COOKIE_NAME,
                signed_value,
                max_age=settings.AFFILIATE_ATTRIBUTION_WINDOW_DAYS * 24 * 60 * 60,
                httponly=True,
                samesite="Lax",
            )

        return response
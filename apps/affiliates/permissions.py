"""
Access control for affiliate-only views.

Deliberately NOT based on User.role - a user can be a customer, seller,
and affiliate simultaneously, so a single role field can't gate this.
Access is purely: does this user have an active AffiliateProfile.
"""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from .models import AffiliateStatus


def active_affiliate_required(view_func):
    @wraps(view_func)
    @login_required(login_url="accounts:login")
    def wrapper(request, *args, **kwargs):
        profile = getattr(request.user, "affiliate_profile", None)

        if profile is None:
            messages.info(request, "You need to apply as an affiliate first.")
            return redirect("affiliates:apply")

        if profile.status != AffiliateStatus.ACTIVE:
            messages.info(request, f"Your affiliate application is currently {profile.get_status_display().lower()}.")
            return redirect("affiliates:application_status")

        return view_func(request, *args, **kwargs)

    return wrapper
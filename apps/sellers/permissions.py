"""
Access control for seller-only views.

Deliberately NOT based on User.role - a user can be a customer, seller,
and affiliate simultaneously, so a single role field can't gate this.
Access is purely: does this user have an approved SellerProfile.
"""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from .models import SellerStatus


def approved_seller_required(view_func):
    @wraps(view_func)
    @login_required(login_url="accounts:login")
    def wrapper(request, *args, **kwargs):
        profile = getattr(request.user, "seller_profile", None)

        if profile is None:
            messages.info(request, "You need to apply as a seller first.")
            return redirect("sellers:apply")

        if profile.status != SellerStatus.APPROVED:
            messages.info(request, f"Your seller application is currently {profile.get_status_display().lower()}.")
            return redirect("sellers:application_status")

        return view_func(request, *args, **kwargs)

    return wrapper

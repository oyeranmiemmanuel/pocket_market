"""
Access control for rider-only views.

Deliberately NOT based on User.role - a user can be a customer, seller,
affiliate, and rider simultaneously, so a single role field can't gate
this. Access is purely: does this user have an approved RiderProfile.
Mirrors apps.sellers.permissions / apps.affiliates.permissions exactly.
"""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from .models import RiderStatus


def approved_rider_required(view_func):
    @wraps(view_func)
    @login_required(login_url="accounts:login")
    def wrapper(request, *args, **kwargs):
        profile = getattr(request.user, "rider_profile", None)

        if profile is None:
            messages.info(request, "You need to apply as a rider first.")
            return redirect("riders:apply")

        if profile.status != RiderStatus.APPROVED:
            messages.info(request, f"Your rider application is currently {profile.get_status_display().lower()}.")
            return redirect("riders:application_status")

        return view_func(request, *args, **kwargs)

    return wrapper
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.core.exceptions import ValidationFailedError

from .forms import RiderApplicationForm, RiderBankDetailsForm
from .permissions import approved_rider_required
from .services import apply_for_rider, deactivate_rider, set_rider_availability


@login_required(login_url="accounts:login")
def apply_view(request):
    existing = getattr(request.user, "rider_profile", None)
    if existing is not None:
        return redirect("riders:application_status")

    if request.method == "POST":
        form = RiderApplicationForm(request.POST)
        if form.is_valid():
            try:
                apply_for_rider(user=request.user, **form.cleaned_data)
            except ValidationFailedError as e:
                messages.error(request, str(e))
                return redirect("riders:apply")

            messages.success(request, "Application submitted! We'll review it shortly.")
            return redirect("riders:application_status")
    else:
        form = RiderApplicationForm()

    return render(request, "riders/apply.html", {"form": form})


@login_required(login_url="accounts:login")
def application_status_view(request):
    profile = getattr(request.user, "rider_profile", None)
    if profile is None:
        return redirect("riders:apply")

    return render(request, "riders/application_status.html", {"profile": profile})


@approved_rider_required
def dashboard_view(request):
    profile = request.user.rider_profile
    return render(request, "riders/dashboard.html", {"profile": profile})


@approved_rider_required
def toggle_availability_view(request):
    profile = request.user.rider_profile

    if request.method == "POST":
        try:
            set_rider_availability(profile=profile, available=not profile.is_available)
        except ValidationFailedError as e:
            messages.error(request, str(e))
        else:
            messages.success(request, f"You are now {'available' if profile.is_available else 'unavailable'}.")

    return redirect("riders:dashboard")


@approved_rider_required
def bank_details_view(request):
    profile = request.user.rider_profile

    if request.method == "POST":
        form = RiderBankDetailsForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Bank details updated.")
            return redirect("riders:dashboard")
    else:
        form = RiderBankDetailsForm(instance=profile)

    return render(request, "riders/bank_details.html", {"form": form})
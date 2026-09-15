"""
KYC submission views (Phase 1). Mirrors the apps.riders/sellers/
affiliates "apply_view" pattern. Ownership is enforced by always scoping
to request.user's own related profile - status changes beyond submission
only ever happen through Django admin actions (apps.kyc.admin), which
apps.kyc.services also backs.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.core.exceptions import ValidationFailedError

from .forms import AffiliateKYCForm, BuyerKYCForm, RiderKYCForm, SellerKYCForm
from .models import AffiliateKYC, BuyerKYC, RiderKYC, SellerKYC
from .services import submit_affiliate_kyc, submit_buyer_kyc, submit_rider_kyc, submit_seller_kyc


@login_required(login_url="accounts:login")
def buyer_kyc_view(request):
    instance = BuyerKYC.objects.filter(user=request.user).first()

    if request.method == "POST":
        form = BuyerKYCForm(request.POST, instance=instance)
        if form.is_valid():
            try:
                submit_buyer_kyc(user=request.user, **form.cleaned_data)
            except ValidationFailedError as e:
                messages.error(request, str(e))
            else:
                messages.success(request, "Your information has been submitted for confirmation.")
                return redirect("kyc:buyer")
    else:
        form = BuyerKYCForm(instance=instance)

    return render(request, "kyc/submit.html", {"form": form, "instance": instance, "title": "Your Information"})


@login_required(login_url="accounts:login")
def seller_kyc_view(request):
    profile = getattr(request.user, "seller_profile", None)
    if profile is None:
        messages.info(request, "You need to apply as a seller first.")
        return redirect("sellers:apply")

    instance = SellerKYC.objects.filter(seller=profile).first()

    if request.method == "POST":
        form = SellerKYCForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            try:
                submit_seller_kyc(seller=profile, **form.cleaned_data)
            except ValidationFailedError as e:
                messages.error(request, str(e))
            else:
                messages.success(request, "Business information submitted for confirmation.")
                return redirect("kyc:seller")
    else:
        form = SellerKYCForm(instance=instance)

    return render(request, "kyc/submit.html", {"form": form, "instance": instance, "title": "Business Verification"})


@login_required(login_url="accounts:login")
def affiliate_kyc_view(request):
    profile = getattr(request.user, "affiliate_profile", None)
    if profile is None:
        messages.info(request, "You need to apply as an affiliate first.")
        return redirect("affiliates:apply")

    instance = AffiliateKYC.objects.filter(affiliate=profile).first()

    if request.method == "POST":
        form = AffiliateKYCForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            try:
                submit_affiliate_kyc(affiliate=profile, **form.cleaned_data)
            except ValidationFailedError as e:
                messages.error(request, str(e))
            else:
                messages.success(request, "Your information has been submitted for confirmation.")
                return redirect("kyc:affiliate")
    else:
        form = AffiliateKYCForm(instance=instance)

    return render(request, "kyc/submit.html", {"form": form, "instance": instance, "title": "Affiliate Verification"})


@login_required(login_url="accounts:login")
def rider_kyc_view(request):
    profile = getattr(request.user, "rider_profile", None)
    if profile is None:
        messages.info(request, "You need to apply as a rider first.")
        return redirect("riders:apply")

    instance = RiderKYC.objects.filter(rider=profile).first()

    if request.method == "POST":
        form = RiderKYCForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            try:
                submit_rider_kyc(rider=profile, **form.cleaned_data)
            except ValidationFailedError as e:
                messages.error(request, str(e))
            else:
                messages.success(request, "Your credentials have been submitted for confirmation.")
                return redirect("kyc:rider")
    else:
        form = RiderKYCForm(instance=instance)

    return render(request, "kyc/submit.html", {"form": form, "instance": instance, "title": "Rider Verification"})
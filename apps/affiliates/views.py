from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from apps.catalog.models import Product
from apps.core.exceptions import ValidationFailedError
from .forms import AffiliatePayoutRequestForm  # add to your existing forms import line
from .services import request_affiliate_payout  # add to your existing services import line
from .forms import AffiliateBankDetailsForm
from .permissions import active_affiliate_required
from .services import apply_for_affiliate, generate_affiliate_link
from apps.payments.services import PaystackTransferError, list_banks, resolve_bank_account
from .services import request_affiliate_payout, send_affiliate_payout  # add to your existing services import


@login_required(login_url="accounts:login")
def apply_view(request):
    """
    No form fields needed to apply - unlike sellers (who need store
    details), becoming an affiliate is just an opt-in; the affiliate
    code is generated automatically.
    """
    existing = getattr(request.user, "affiliate_profile", None)
    if existing is not None:
        return redirect("affiliates:application_status")

    if request.method == "POST":
        try:
            apply_for_affiliate(user=request.user)
        except ValidationFailedError as e:
            messages.error(request, str(e))
            return redirect("affiliates:apply")

        messages.success(request, "Application submitted! We'll review it shortly.")
        return redirect("affiliates:application_status")

    return render(request, "affiliates/apply.html")


@login_required(login_url="accounts:login")
def application_status_view(request):
    profile = getattr(request.user, "affiliate_profile", None)
    if profile is None:
        return redirect("affiliates:apply")

    return render(request, "affiliates/application_status.html", {"profile": profile})


@active_affiliate_required
def dashboard_view(request):
    profile = request.user.affiliate_profile
    return render(request, "affiliates/dashboard.html", {
        "profile": profile,
        "total_links": profile.links.filter(is_active=True).count(),
    })


# ---------------------------------------------------------------------------
# Conversions / commissions - phase 7.
# ---------------------------------------------------------------------------

@active_affiliate_required
def my_conversions_view(request):
    """
    Read-only list of this affiliate's own commissions - never another
    affiliate's (scoped by `profile`, same object-level-ownership pattern
    as sellers.views.order_item_list_view). Customers' own order totals/
    financial details are never exposed here, only what this affiliate
    personally earned per conversion (spec section 29/30).
    """
    profile = request.user.affiliate_profile

    commissions = (
        profile.commissions.filter(reversal_of__isnull=True)
        .select_related("order", "order_item")
        .order_by("-created_at")
    )

    status_filter = request.GET.get("status")
    if status_filter:
        commissions = commissions.filter(status=status_filter)

    paginator = Paginator(commissions, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "affiliates/conversions.html", {
        "profile": profile,
        "page_obj": page_obj,
        "status_filter": status_filter,
    })

@active_affiliate_required
def payout_list_view(request):
    """Phase 9 - mirrors sellers.views.payout_list_view exactly."""
    profile = request.user.affiliate_profile

    if request.method == "POST":
        form = AffiliatePayoutRequestForm(request.POST)
        if form.is_valid():
            try:
                payout = request_affiliate_payout(affiliate=profile, amount=form.cleaned_data["amount"])
            except ValidationFailedError as e:
                messages.error(request, str(e))
            else:
                messages.success(request, f"Payout request {payout.reference} submitted for \u20a6{payout.amount}.")
            return redirect("affiliates:payouts")
    else:
        form = AffiliatePayoutRequestForm()

    payouts = profile.payouts.order_by("-created_at")
    paginator = Paginator(payouts, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "affiliates/payouts.html", {
        "profile": profile,
        "withdrawable_balance": profile.withdrawable_balance,
        "payouts_in_progress": profile.payouts_in_progress_total,
        "form": form,
        "page_obj": page_obj,
    })
# ---------------------------------------------------------------------------
# Referral links - phase 6.
# ---------------------------------------------------------------------------

@active_affiliate_required
def my_links_view(request):
    profile = request.user.affiliate_profile

    links = profile.links.filter(is_active=True).select_related("product")
    already_linked_ids = links.values_list("product_id", flat=True)

    promotable_products = (
        Product.active.filter(is_active=True)
        .exclude(pk__in=already_linked_ids)
        .select_related("category")
    )

    return render(request, "affiliates/links.html", {
        "profile": profile,
        "links": links,
        "promotable_products": promotable_products,
    })


@active_affiliate_required
def generate_link_view(request, product_id):
    profile = request.user.affiliate_profile
    product = get_object_or_404(Product.active, pk=product_id, is_active=True)

    if request.method == "POST":
        generate_affiliate_link(affiliate=profile, product=product)
        messages.success(request, f'Link generated for "{product.name}".')

    return redirect("affiliates:my_links")

@active_affiliate_required
def bank_details_view(request):
    profile = request.user.affiliate_profile

    try:
        banks = list_banks()
    except PaystackTransferError as e:
        banks = []
        messages.warning(request, f"Could not load the bank list right now: {e}")

    if request.method == "POST":
        form = AffiliateBankDetailsForm(request.POST, instance=profile)
        if form.is_valid():
            bank_code = form.cleaned_data["bank_code"]
            account_number = form.cleaned_data["bank_account_number"]

            try:
                resolved = resolve_bank_account(account_number=account_number, bank_code=bank_code)
            except PaystackTransferError as e:
                messages.error(request, f"Could not verify that account: {e}")
                return render(request, "affiliates/bank_details.html", {"form": form, "banks": banks, "profile": profile})

            bank_name = next((b["name"] for b in banks if b["code"] == bank_code), "")

            profile.bank_code = bank_code
            profile.bank_name = bank_name
            profile.bank_account_number = resolved["account_number"]
            profile.bank_account_name = resolved["account_name"]
            profile.save(update_fields=[
                "bank_code", "bank_name", "bank_account_number", "bank_account_name", "updated_at",
            ])

            messages.success(request, f"Bank details verified and saved for {resolved['account_name']}.")
            return redirect("affiliates:dashboard")
    else:
        form = AffiliateBankDetailsForm(instance=profile)

    return render(request, "affiliates/bank_details.html", {"form": form, "banks": banks, "profile": profile})
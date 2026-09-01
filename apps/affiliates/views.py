from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from apps.catalog.models import Product
from apps.core.exceptions import ValidationFailedError

from .forms import AffiliateBankDetailsForm
from .permissions import active_affiliate_required
from .services import apply_for_affiliate, generate_affiliate_link


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

    if request.method == "POST":
        form = AffiliateBankDetailsForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Bank details updated.")
            return redirect("affiliates:dashboard")
    else:
        form = AffiliateBankDetailsForm(instance=profile)

    return render(request, "affiliates/bank_details.html", {"form": form})
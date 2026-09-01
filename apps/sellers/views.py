from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from apps.catalog.models import Product
from apps.core.enums import FulfillmentStatus
from apps.core.exceptions import ValidationFailedError
from apps.orders.models import OrderItem

from .forms import SellerApplicationForm, SellerBankDetailsForm, SellerProductForm
from .permissions import approved_seller_required
from .services import apply_for_seller


@login_required(login_url="accounts:login")
def apply_view(request):
    existing = getattr(request.user, "seller_profile", None)
    if existing is not None:
        return redirect("sellers:application_status")

    if request.method == "POST":
        form = SellerApplicationForm(request.POST)
        if form.is_valid():
            try:
                apply_for_seller(user=request.user, **form.cleaned_data)
            except ValidationFailedError as e:
                messages.error(request, str(e))
                return redirect("sellers:apply")

            messages.success(request, "Application submitted! We'll review it shortly.")
            return redirect("sellers:application_status")
    else:
        form = SellerApplicationForm()

    return render(request, "sellers/apply.html", {"form": form})


@login_required(login_url="accounts:login")
def application_status_view(request):
    profile = getattr(request.user, "seller_profile", None)
    if profile is None:
        return redirect("sellers:apply")

    return render(request, "sellers/application_status.html", {"profile": profile})


@approved_seller_required
def dashboard_view(request):
    profile = request.user.seller_profile

    order_items = OrderItem.objects.filter(seller=profile)

    context = {
        "profile": profile,
        "total_products": profile.products.filter(deleted_at__isnull=True).count(),
        "total_orders": order_items.values("order_id").distinct().count(),
        "total_items_sold": order_items.count(),
        "pending_fulfillment_count": order_items.filter(
            fulfillment_status=FulfillmentStatus.PENDING
        ).count(),
        # Phase 8 - real numbers from the financial ledger, not estimates.
        "total_sales": profile.total_sales,
        "total_earnings": profile.total_earnings,
        "pending_payout": profile.pending_earnings,
        "available_balance": profile.available_earnings,
        "paid_out": profile.paid_earnings,
        "refunded_amount": profile.refunded_amount,
    }
    return render(request, "sellers/dashboard.html", context)

@approved_seller_required
def earnings_view(request):
    """
    Read-only list of this seller's own earnings - never another
    seller's (same object-level-ownership pattern as order_item_list_view
    / apps.affiliates.views.my_conversions_view).
    """
    profile = request.user.seller_profile

    earnings = (
        profile.earnings.filter(reversal_of__isnull=True)
        .select_related("order", "order_item")
        .order_by("-created_at")
    )

    status_filter = request.GET.get("status")
    if status_filter:
        earnings = earnings.filter(status=status_filter)

    paginator = Paginator(earnings, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "sellers/earnings.html", {
        "profile": profile,
        "page_obj": page_obj,
        "status_filter": status_filter,
    })


# ---------------------------------------------------------------------------
# Product management - phase 4.
#
# Every view here is scoped to `request.user.seller_profile`: sellers only
# ever see/touch their own products. Ownership is enforced with a queryset
# filter (list) or a get_object_or_404(..., seller=profile) lookup
# (edit/delete), which 404s for another seller's product ID rather than
# relying on the UI simply not showing a link to it (see 42_SECURITY /
# 41_OBJECT_LEVEL_PERMISSIONS in the implementation spec).
# ---------------------------------------------------------------------------

@approved_seller_required
def product_list_view(request):
    profile= request.user.seller_profile
    products = Product.objects.filter(seller=profile).select_related("category").order_by("-created_at")

    paginator = Paginator(products, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "sellers/product_list.html", {"profile": profile, "page_obj": page_obj})


@approved_seller_required
def product_create_view(request):
    profile = request.user.seller_profile

    if request.method == "POST":
        form = SellerProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            # Ownership is never taken from the submitted form - always
            # the logged-in seller's own profile.
            product.seller = profile
            product.save()
            messages.success(request, f'"{product.name}" was created.')
            return redirect("sellers:product_list")
    else:
        form = SellerProductForm()

    return render(request, "sellers/product_form.html", {"form": form, "mode": "create"})


@approved_seller_required
def product_edit_view(request, pk):
    profile = request.user.seller_profile
    product = get_object_or_404(Product, pk=pk, seller=profile)

    if request.method == "POST":
        form = SellerProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, f'"{product.name}" was updated.')
            return redirect("sellers:product_list")
    else:
        form = SellerProductForm(instance=product)

    return render(request, "sellers/product_form.html", {"form": form, "mode": "edit", "product": product})


@approved_seller_required
def product_delete_view(request, pk):
    profile = request.user.seller_profile
    product = get_object_or_404(Product, pk=pk, seller=profile)

    if request.method == "POST":
        product.delete()  # soft delete (BaseModel.delete) - stock/order history is preserved
        messages.success(request, f'"{product.name}" was deleted.')
        return redirect("sellers:product_list")

    return render(request, "sellers/product_confirm_delete.html", {"product": product})


# ---------------------------------------------------------------------------
# Order management - phase 4.
#
# A seller only ever sees the OrderItems that belong to them, never the
# full Order or another seller's items from the same order (see
# 07_SELLER_ORDER_MANAGEMENT / 08_MULTI_SELLER_ORDERS in the spec).
# ---------------------------------------------------------------------------

@approved_seller_required
def order_item_list_view(request):
    profile = request.user.seller_profile
    items = (
        OrderItem.objects.filter(seller=profile)
        .select_related("order", "product")
        .order_by("-created_at")
    )

    status_filter = request.GET.get("status")
    if status_filter in FulfillmentStatus.values:
        items = items.filter(fulfillment_status=status_filter)

    paginator = Paginator(items, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "sellers/order_item_list.html",
        {
            "profile": profile,
            "page_obj": page_obj,
            "status_choices": FulfillmentStatus.choices,
            "status_filter": status_filter,
        },
    )


@approved_seller_required
def update_fulfillment_status_view(request, item_id):
    profile = request.user.seller_profile
    item = get_object_or_404(OrderItem, pk=item_id, seller=profile)

    if request.method == "POST":
        if not item.order.is_paid:
            # Never trust the client on this - re-check server-side even
            # though the template already hides the control for unpaid
            # orders (see docs section 42, "never trust ... payment status
            # sent from frontend").
            messages.error(request, "Can't update fulfillment before the order is paid.")
            return redirect("sellers:order_item_list")

        new_status = request.POST.get("fulfillment_status")
        if new_status in FulfillmentStatus.values:
            item.fulfillment_status = new_status
            item.save(update_fields=["fulfillment_status", "updated_at"])
            messages.success(request, "Fulfillment status updated.")
        else:
            messages.error(request, "Invalid status.")

    return redirect("sellers:order_item_list")


@approved_seller_required
def bank_details_view(request):
    profile = request.user.seller_profile

    if request.method == "POST":
        form = SellerBankDetailsForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Bank details updated.")
            return redirect("sellers:dashboard")
    else:
        form = SellerBankDetailsForm(instance=profile)

    return render(request, "sellers/bank_details.html", {"form": form})

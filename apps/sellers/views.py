from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.catalog.models import Product, ProductImage, Review
from apps.core.constants import (
    AFFILIATE_COMMISSION_RATE_MAX,
    AFFILIATE_COMMISSION_RATE_MIN,
    BUYER_PROTECTION_WINDOW_HOURS,
)
from apps.core.enums import FulfillmentStatus, PayoutStatus
from apps.core.exceptions import ValidationFailedError
from apps.orders.models import OrderItem, Refund
from apps.orders.services.refunds import confirm_item_condition, mark_item_received

from .forms import (
    ProductColorVariantFormSet,
    ProductImageFormSet,
    ProductSizeVariantFormSet,
    SellerApplicationForm,
    SellerBankDetailsForm,
    SellerProductForm,
    SellerStoreSettingsForm,
)
from .models import SellerProfile, SellerStatus
from .order_status import SellerOrderStatus, build_seller_order_row, seller_order_item_queryset
from .permissions import approved_seller_required
from .services import apply_for_seller, request_seller_payout


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
        "gross_sales": profile.total_sales,
        "platform_fees": profile.platform_fees_total,
        "affiliate_fees": profile.affiliate_fees_total,
        "refunds": profile.refunded_amount,
        "net_earnings": profile.total_earnings,
        "BUYER_PROTECTION_WINDOW_HOURS": BUYER_PROTECTION_WINDOW_HOURS,
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
        # Bound against the submitted data only (no `instance=` yet - the
        # product doesn't exist until form.save() below), which is enough
        # for is_valid() to run each nested form's own field validation.
        # The formsets are re-bound to the real product right after it's
        # created, and only saved once every one of them (including this
        # one) has passed.
        image_formset = ProductImageFormSet(request.POST, request.FILES, prefix="images")
        color_formset = ProductColorVariantFormSet(request.POST, prefix="colors")
        size_formset = ProductSizeVariantFormSet(request.POST, prefix="sizes")

        if (
            form.is_valid()
            and image_formset.is_valid()
            and color_formset.is_valid()
            and size_formset.is_valid()
        ):
            product = form.save(commit=False)
            # Ownership is never taken from the submitted form - always
            # the logged-in seller's own profile.
            product.seller = profile
            product.save()

            for formset in (image_formset, color_formset, size_formset):
                formset.instance = product
                formset.save()

            messages.success(request, f'"{product.name}" was created.')
            return redirect("sellers:product_list")
    else:
        form = SellerProductForm()
        image_formset = ProductImageFormSet(prefix="images")
        color_formset = ProductColorVariantFormSet(prefix="colors")
        size_formset = ProductSizeVariantFormSet(prefix="sizes")

    return render(request, "sellers/product_form.html", {
        "form": form,
        "mode": "create",
        "commission_min": AFFILIATE_COMMISSION_RATE_MIN,
        "commission_max": AFFILIATE_COMMISSION_RATE_MAX,
        "image_formset": image_formset,
        "color_formset": color_formset,
        "size_formset": size_formset,
        "max_images": ProductImage.MAX_IMAGES,
    })


@approved_seller_required
def product_edit_view(request, pk):
    profile = request.user.seller_profile
    product = get_object_or_404(Product, pk=pk, seller=profile)

    if request.method == "POST":
        form = SellerProductForm(request.POST, request.FILES, instance=product)
        image_formset = ProductImageFormSet(request.POST, request.FILES, instance=product, prefix="images")
        color_formset = ProductColorVariantFormSet(request.POST, instance=product, prefix="colors")
        size_formset = ProductSizeVariantFormSet(request.POST, instance=product, prefix="sizes")

        if (
            form.is_valid()
            and image_formset.is_valid()
            and color_formset.is_valid()
            and size_formset.is_valid()
        ):
            form.save()
            image_formset.save()
            color_formset.save()
            size_formset.save()
            messages.success(request, f'"{product.name}" was updated.')
            return redirect("sellers:product_list")
    else:
        form = SellerProductForm(instance=product)
        image_formset = ProductImageFormSet(instance=product, prefix="images")
        color_formset = ProductColorVariantFormSet(instance=product, prefix="colors")
        size_formset = ProductSizeVariantFormSet(instance=product, prefix="sizes")

    return render(request, "sellers/product_form.html", {
        "form": form,
        "mode": "edit",
        "product": product,
        "commission_min": AFFILIATE_COMMISSION_RATE_MIN,
        "commission_max": AFFILIATE_COMMISSION_RATE_MAX,
        "image_formset": image_formset,
        "color_formset": color_formset,
        "size_formset": size_formset,
        "max_images": ProductImage.MAX_IMAGES,
    })


@approved_seller_required
def product_delete_view(request, pk):
    profile = request.user.seller_profile
    product = get_object_or_404(Product, pk=pk, seller=profile)

    if request.method == "POST":
        product.delete()  # soft delete (BaseModel.delete) - stock/order history is preserved
        messages.success(request, f'"{product.name}" was deleted.')
        return redirect("sellers:product_list")

    return render(request, "sellers/product_confirm_delete.html", {"product": product})


def _is_ajax(request):
    """
    Matches the convention already used sitewide (templates/core/base.html's
    add-to-cart-form, templates/cart/cart_detail.html's update-quantity
    requests): a fetch() call sets this header explicitly, a normal
    browser form submission never does. Lets each of these views serve
    both a real <form> (works with JS disabled) and a fetch()-driven one
    from the same URL.
    """
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


@approved_seller_required
def product_toggle_active_view(request, pk):
    profile = request.user.seller_profile
    product = get_object_or_404(Product, pk=pk, seller=profile)
    is_ajax = _is_ajax(request)

    if request.method != "POST":
        if is_ajax:
            return JsonResponse({"ok": False, "error": "Invalid request method."}, status=405)
        return redirect("sellers:product_list")

    product.is_active = not product.is_active
    product.save(update_fields=["is_active", "updated_at"])
    message = f'"{product.name}" is now {"active" if product.is_active else "inactive"}.'

    if is_ajax:
        return JsonResponse({"ok": True, "is_active": product.is_active, "message": message})

    messages.success(request, message)
    return redirect("sellers:product_list")


@approved_seller_required
def product_update_stock_view(request, pk):
    """
    Inline stock quantity edit from the product list row (spec section
    7 - "Product images / Stock information ... Use AJAX for suitable
    actions such as status changes and inline updates"). Same
    validation either way the request arrives (AJAX or a plain form
    submit) - only the response shape differs.
    """
    profile = request.user.seller_profile
    product = get_object_or_404(Product, pk=pk, seller=profile)
    is_ajax = _is_ajax(request)

    if request.method != "POST":
        if is_ajax:
            return JsonResponse({"ok": False, "error": "Invalid request method."}, status=405)
        return redirect("sellers:product_list")

    raw_stock = (request.POST.get("stock") or "").strip()
    try:
        new_stock = int(raw_stock)
        if new_stock < 0:
            raise ValueError
    except (TypeError, ValueError):
        error = "Stock must be a whole number of 0 or more."
        if is_ajax:
            return JsonResponse({"ok": False, "error": error}, status=400)
        messages.error(request, error)
        return redirect("sellers:product_list")

    product.stock = new_stock
    product.save(update_fields=["stock", "updated_at"])
    message = f'Stock for "{product.name}" updated to {product.stock}.'

    if is_ajax:
        return JsonResponse({"ok": True, "stock": product.stock, "message": message})

    messages.success(request, message)
    return redirect("sellers:product_list")


# ---------------------------------------------------------------------------
# Order management - phase 4.
#
# A seller only ever sees the OrderItems that belong to them, never the
# full Order or another seller's items from the same order (see
# 07_SELLER_ORDER_MANAGEMENT / 08_MULTI_SELLER_ORDERS in the spec).
# ---------------------------------------------------------------------------

@approved_seller_required
def order_item_list_view(request):
    """
    Spec section 8. Only this seller's own line items are ever visible -
    the queryset is filtered on `seller=profile` before anything else, so
    a seller can never see another seller's items or the rest of a
    shared multi-seller order.

    The status filter/columns use the derived SellerOrderStatus (see
    apps.sellers.order_status), not the raw fulfillment_status field -
    the raw field only covers the seller's own pending/processing/...
    updates, while the page also needs to reflect pickup, delivery and
    refund state owned by other apps.
    """
    profile = request.user.seller_profile
    items = seller_order_item_queryset(profile)

    rows = [build_seller_order_row(item) for item in items]

    status_filter = request.GET.get("status")
    if status_filter in SellerOrderStatus.values:
        rows = [row for row in rows if row["status"] == status_filter]

    paginator = Paginator(rows, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "sellers/order_item_list.html",
        {
            "profile": profile,
            "page_obj": page_obj,
            "status_choices": SellerOrderStatus.choices,
            "status_filter": status_filter,
            "fulfillment_status_choices": FulfillmentStatus.choices,
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


@approved_seller_required
def store_settings_view(request):
    profile = request.user.seller_profile

    if request.method == "POST":
        form = SellerStoreSettingsForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Store settings updated.")
            return redirect("sellers:store_settings")
    else:
        form = SellerStoreSettingsForm(instance=profile)

    return render(request, "sellers/store_settings.html", {"form": form, "profile": profile})


@approved_seller_required
def payouts_view(request):
    profile = request.user.seller_profile

    return render(request, "sellers/payouts.html", {
        "profile": profile,
        "available_balance": profile.withdrawable_balance,
        "pending_earnings": profile.pending_earnings,
        "payouts": profile.payouts.all(),
        "has_pending_request": profile.payouts.filter(
            status__in=[PayoutStatus.PENDING, PayoutStatus.PROCESSING],
        ).exists(),
    })


@approved_seller_required
def payout_request_view(request):
    profile = request.user.seller_profile

    if request.method == "POST":
        try:
            amount = Decimal(request.POST.get("amount") or "0")
            request_seller_payout(seller=profile, amount=amount)
            messages.success(request, "Payout requested.")
        except (InvalidOperation, ValidationFailedError) as e:
            messages.error(request, str(e) if isinstance(e, ValidationFailedError) else "Enter a valid amount.")

    return redirect("sellers:payouts")


# ---------------------------------------------------------------------------
# Public storefront - mounted separately at /store/<slug>/ via
# apps.sellers.public_urls, not apps.sellers.urls. Public, no
# @approved_seller_required - any visitor can view an approved seller's store.
# ---------------------------------------------------------------------------

def public_store_view(request, slug):
    seller = get_object_or_404(SellerProfile, store_slug=slug, status=SellerStatus.APPROVED)

    products = Product.active.filter(seller=seller, is_active=True)

    query = request.GET.get("q", "").strip()
    if query:
        products = products.filter(Q(name__icontains=query) | Q(description__icontains=query))

    sort = request.GET.get("sort", "newest")
    if sort == "price_asc":
        products = products.order_by("price")
    elif sort == "price_desc":
        products = products.order_by("-price")
    else:
        sort = "newest"
        products = products.order_by("-created_at")

    rating_data = Review.objects.filter(product__seller=seller).aggregate(
        average_rating=Avg("rating"), review_count=Count("id"),
    )

    return render(request, "sellers/public_store.html", {
        "seller": seller,
        "products": products,
        "query": query,
        "sort": sort,
        "average_rating": rating_data["average_rating"] or 0,
        "review_count": rating_data["review_count"],
    })


# ---------------------------------------------------------------------------
# Spec section 26 - the seller's own side of a refund. The seller can
# only ever move a refund through mark_item_received/confirm_item_condition -
# both explicitly refuse to run outside their one valid preceding state
# (see apps.orders.services.refunds) - they can never approve, reject,
# or execute a refund themselves.
# ---------------------------------------------------------------------------

@approved_seller_required
def seller_refund_list_view(request):
    profile = request.user.seller_profile
    refunds = (
        Refund.objects.filter(order_item__seller=profile)
        .select_related("order_item", "order_item__order")
        .order_by("-created_at")
    )

    paginator = Paginator(refunds, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "sellers/refund_list.html", {"profile": profile, "page_obj": page_obj})


@approved_seller_required
def seller_refund_detail_view(request, refund_id):
    profile = request.user.seller_profile
    refund = get_object_or_404(
        Refund.objects.select_related("order_item", "order_item__order").prefetch_related("evidence"),
        pk=refund_id, order_item__seller=profile,
    )

    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "mark_received":
                mark_item_received(refund=refund, seller_user=request.user)
                messages.success(request, "Marked as received.")
            elif action == "confirm_condition":
                notes = request.POST.get("notes", "").strip()
                if not notes:
                    raise ValidationFailedError("Please describe the item's condition.")
                confirm_item_condition(refund=refund, seller_user=request.user, notes=notes)
                messages.success(request, "Condition confirmation submitted.")
        except ValidationFailedError as e:
            messages.error(request, str(e))
        return redirect("sellers:refund_detail", refund_id=refund.id)

    return render(request, "sellers/refund_detail.html", {"profile": profile, "refund": refund})
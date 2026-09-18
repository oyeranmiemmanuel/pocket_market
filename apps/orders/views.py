import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.affiliates.services import get_attributed_affiliate
from apps.cart.services import get_or_create_cart
from apps.core.constants import BUYER_PROTECTION_WINDOW_HOURS
from apps.core.enums import DeliveryMethod
from apps.core.exceptions import ValidationFailedError
from apps.logistics.models import SellerFulfillment
from apps.sellers.order_status import SellerOrderStatus, build_seller_order_row

from .forms import CheckoutForm
from .models import Order, OrderItem, SavedAddress
from .services import build_checkout_summary, create_order_from_cart, request_refund
from .services.checkout import validate_cart_stock

# Marketplace Frontend Roadmap section 20 - "Order Tracking": the fixed
# progression a seller's fulfillment of an order moves through, used to
# draw the buyer-facing per-seller checklist (✓ done / ● current /
# upcoming). Deliberately the SellerOrderStatus values (apps.sellers.
# order_status) - the same derived status the seller's own order
# management page already shows - minus its two exception states
# (REFUND_REQUESTED, CANCELLED), which aren't progression steps and are
# instead shown as their own banner (see _group_current_step_index
# below) so a refund request doesn't make the checklist regress.
ORDER_TRACKING_TIMELINE_STEPS = [
    SellerOrderStatus.CONFIRMED,
    SellerOrderStatus.PREPARING,
    SellerOrderStatus.READY_FOR_PICKUP,
    SellerOrderStatus.ASSIGNED_TO_RIDER,
    SellerOrderStatus.PICKED_UP,
    SellerOrderStatus.IN_TRANSIT,
    SellerOrderStatus.DELIVERED,
]
_TIMELINE_VALUES = [s.value for s in ORDER_TRACKING_TIMELINE_STEPS]


@login_required(login_url='accounts:login')
def checkout_view(request):
    cart = get_or_create_cart(request)

    if not cart.items.exists():
        messages.info(request, "Your cart is empty.")
        return redirect("cart:cart_detail")

    # Surface stock problems before the user fills the whole form in.
    try:
        validate_cart_stock(cart)
    except ValidationFailedError as e:
        messages.error(request, str(e))
        return redirect("cart:cart_detail")

    if request.method == "POST":
        form = CheckoutForm(request.POST, user=request.user)

        if form.is_valid():
            try:
                order = create_order_from_cart(
                    user=request.user,
                    cart=cart,
                    email=form.cleaned_data["email"],
                    full_name=form.cleaned_data["full_name"],
                    phone=form.cleaned_data["phone"],
                    delivery_method=form.cleaned_data["delivery_method"],
                    shipping_data=form.shipping_data(),
                    # Phase 7 - whichever affiliate's ?ref= link is
                    # currently attributed to this visitor (spec section
                    # 28: must survive guest -> authenticated checkout,
                    # which it does here since the cookie isn't tied to
                    # login state at all).
                    affiliate=get_attributed_affiliate(request),
                )
            except ValidationFailedError as e:
                messages.error(request, str(e))
                return redirect("cart:cart_detail")

            if form.cleaned_data.get("save_address"):
                SavedAddress.objects.create(user=request.user, **form.shipping_data())

            return redirect("payments:initiate", order_reference=order.reference)
    else:
        initial = {
            "full_name": request.user.get_full_name() or request.user.username,
            "email": request.user.email,
        }
        default_address = SavedAddress.objects.filter(user=request.user, is_default=True).first()
        if default_address:
            initial["saved_address"] = default_address.pk
        form = CheckoutForm(initial=initial, user=request.user)

    # Server-rendered starting point for the order summary panel
    # (Marketplace Frontend Roadmap section 19) - whichever delivery
    # method is currently selected (the posted one on a validation-error
    # re-render, else the default). The page's own JS re-fetches this
    # same breakdown from checkout_summary_view below on every delivery
    # method change, rather than ever computing it itself.
    selected_method = request.POST.get("delivery_method") or DeliveryMethod.SHIPPING
    checkout_summary = build_checkout_summary(cart, selected_method)

    return render(request, "orders/checkout.html", {
        "form": form,
        "cart": cart,
        "checkout_summary": checkout_summary,
    })


@login_required(login_url='accounts:login')
def checkout_summary_view(request):
    """
    Marketplace Frontend Roadmap section 19 - "Before payment, request a
    server-generated checkout summary. Never trust a browser-calculated
    final amount." The checkout page's JS calls this on every delivery
    method change and renders only what comes back here - it never does
    the seller/subtotal/delivery-fee arithmetic itself. Recomputes from
    the server's own copy of this user's cart, never from anything the
    client sends about cart contents.
    """
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Invalid request method."}, status=405)

    cart = get_or_create_cart(request)
    if not cart.items.exists():
        return JsonResponse({"ok": False, "error": "Your cart is empty."}, status=400)

    delivery_method = request.POST.get("delivery_method")
    if delivery_method not in DeliveryMethod.values:
        return JsonResponse({"ok": False, "error": "Invalid delivery method."}, status=400)

    summary = build_checkout_summary(cart, delivery_method)

    def money(value):
        return f"{value:,.2f}"

    return JsonResponse({
        "ok": True,
        "delivery_method": summary["delivery_method"],
        "sellers": [
            {
                "seller_name": s["seller_name"],
                "subtotal": money(s["subtotal"]),
                "delivery_fee": money(s["delivery_fee"]),
                "item_count": s["item_count"],
            }
            for s in summary["sellers"]
        ],
        "products_total": money(summary["products_total"]),
        "total_delivery_fee": money(summary["total_delivery_fee"]),
        "final_total": money(summary["final_total"]),
    })


def _order_rows(order):
    """
    One SellerOrderStatus-derived row per OrderItem in this order (see
    apps.sellers.order_status.build_seller_order_row) - the exact same
    derivation the seller's own order management page uses, so a buyer
    and a seller never see two different stories about the same item.

    Mirrors apps.sellers.order_status.seller_order_item_queryset's
    prefetch shape, but for every seller in this one order rather than
    one seller across many orders - the SellerFulfillment prefetch below
    is deliberately NOT filtered by seller, since a multi-seller order
    needs all of them.
    """
    items = (
        OrderItem.objects.filter(order=order)
        .select_related(
            "order", "order__delivery", "order__delivery__delivery_task", "order__shipping_address",
            "product", "seller",
        )
        .prefetch_related(
            "refunds",
            "seller_earnings",
            Prefetch(
                "order__seller_fulfillments",
                queryset=SellerFulfillment.objects.prefetch_related("packages__pickup_tasks__rider"),
                to_attr="_prefetched_fulfillments",
            ),
        )
    )
    return [build_seller_order_row(item) for item in items]


def _protection_info(item):
    """
    Marketplace Frontend Roadmap section 21 - "Buyer Protection UI".
    None until the item actually has a delivered_at to count from. The
    countdown itself is informational only, exactly as the roadmap
    specifies - actual payout eligibility is decided server-side,
    elsewhere (apps.sellers.models.EarningStatus / apps.ledger), never
    by whether this window has visually run out.
    """
    if item.delivered_at is None:
        return None

    expires_at = item.delivered_at + datetime.timedelta(hours=BUYER_PROTECTION_WINDOW_HOURS)
    remaining_seconds = max(0, int((expires_at - timezone.now()).total_seconds()))
    return {
        "delivered_at": item.delivered_at,
        "expires_at": expires_at,
        "active": remaining_seconds > 0,
        "remaining_seconds": remaining_seconds,
    }


def _group_current_step_index(rows):
    """
    How far along ORDER_TRACKING_TIMELINE_STEPS this seller's whole
    slice of the order has gotten - the LOWEST index among its own
    items, so a group only shows as far along as its least-progressed
    item (one item still "Preparing" holds the whole seller's checklist
    at "Preparing", even if another of their items is further ahead).
    Cancelled items are excluded entirely rather than dragging the group
    backwards; Completed counts as fully done (same position as
    Delivered, the last real step).
    """
    indices = []
    for row in rows:
        status = row["status"]
        if status == SellerOrderStatus.CANCELLED.value:
            continue
        if status == SellerOrderStatus.COMPLETED.value:
            indices.append(len(_TIMELINE_VALUES) - 1)
        elif status in _TIMELINE_VALUES:
            indices.append(_TIMELINE_VALUES.index(status))
        else:
            indices.append(-1)  # Pending or Refund Requested - nothing checked off yet
    return min(indices) if indices else -1


def _group_timeline(current_index):
    steps = []
    for i, status in enumerate(ORDER_TRACKING_TIMELINE_STEPS):
        if i < current_index:
            state = "done"
        elif i == current_index:
            state = "current"
        else:
            state = "upcoming"
        steps.append({"label": status.label, "state": state})
    return steps


@login_required(login_url='accounts:login')
def order_list(request):
    orders = Order.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "orders/order_list.html", {"orders": orders})


@login_required(login_url='accounts:login')
def order_detail(request, reference):
    order = get_object_or_404(
        Order.objects.select_related("shipping_address"), reference=reference, user=request.user,
    )

    rows = _order_rows(order)
    for row in rows:
        row["protection"] = _protection_info(row["item"])

    # Marketplace Frontend Roadmap section 20 - "Order Tracking": "The
    # buyer should see fulfillment separately [per seller]." Same
    # grouping convention as the cart/checkout pages
    # (apps.orders.services.group_cart_by_seller) - first-seller-
    # encountered order, so a buyer sees the same seller ordering here as
    # they did in their cart and at checkout.
    deliveries_by_seller_id = {d.seller_id: d for d in order.seller_deliveries.all()}
    seller_groups = {}
    order_of_sellers = []
    for row in rows:
        seller = row["item"].seller
        key = seller.id if seller else None
        if key not in seller_groups:
            seller_groups[key] = {
                "seller_name": seller.store_name if seller else "This Store",
                "delivery_fee": deliveries_by_seller_id[key].delivery_fee if key in deliveries_by_seller_id else None,
                "rows": [],
            }
            order_of_sellers.append(key)
        seller_groups[key]["rows"].append(row)

    for key in order_of_sellers:
        group = seller_groups[key]
        current_index = _group_current_step_index(group["rows"])
        group["timeline"] = _group_timeline(current_index)
        group["all_cancelled"] = all(
            row["status"] == SellerOrderStatus.CANCELLED.value for row in group["rows"]
        )

    return render(request, "orders/order_detail.html", {
        "order": order,
        "seller_groups": [seller_groups[key] for key in order_of_sellers],
    })


@login_required(login_url='accounts:login')
def request_refund_view(request, reference, item_id):
    """
    Backs both "Report an issue" and "Request a refund" (Marketplace
    Frontend Roadmap section 21) - this codebase has one buyer-initiated
    dispute mechanism (Refund, with a free-text reason), not two
    separate models, so both actions create the same kind of request and
    are told apart later by whatever the buyer actually wrote as their
    reason. request_refund (apps.orders.services.refunds) already
    enforces the real rules: one active request per item, order must be
    paid, ownership checked. This view adds no rule of its own about the
    48-hour window - the window is a UI affordance (the button is hidden
    once it's passed), not a hard backend cutoff; whether a late request
    can still be honoured is exactly the kind of payout-eligibility
    decision the roadmap says the backend controls, separately.
    """
    order = get_object_or_404(Order, reference=reference, user=request.user)
    item = get_object_or_404(OrderItem, pk=item_id, order=order)

    if request.method != "POST":
        return redirect("orders:order_detail", reference=order.reference)

    reason = (request.POST.get("reason") or "").strip()
    if not reason:
        messages.error(request, "Please describe the issue before submitting.")
        return redirect("orders:order_detail", reference=order.reference)

    try:
        request_refund(order_item=item, user=request.user, reason=reason)
        messages.success(request, "Your request has been submitted - we'll review it shortly.")
    except ValidationFailedError as e:
        messages.error(request, str(e))

    return redirect("orders:order_detail", reference=order.reference)


@login_required(login_url='accounts:login')
def download_product(request, reference, item_id):
    """
    Digital file download for a purchased item.

    Replaces the old monolith's download_product() view, which had NO
    ownership or payment check at all - anyone who knew/guessed a
    product_id could download any digital file for free, paid or not.
    This version requires: the order belongs to the requesting user, the
    order is actually paid, the item belongs to that order, and the
    product is a digital product with a file attached.
    """
    order = get_object_or_404(Order, reference=reference, user=request.user)

    if not order.is_paid:
        messages.error(request, "This order hasn't been paid for yet.")
        return redirect("orders:order_detail", reference=order.reference)

    item = get_object_or_404(OrderItem, pk=item_id, order=order)

    if item.product is None or not item.product.is_digital or not item.product.digital_file:
        messages.error(request, "This item isn't available for download.")
        return redirect("orders:order_detail", reference=order.reference)

    response = HttpResponse(item.product.digital_file, content_type="application/octet-stream")
    filename = item.product.digital_file.name.split("/")[-1]
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
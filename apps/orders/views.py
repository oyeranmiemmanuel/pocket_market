from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.affiliates.services import get_attributed_affiliate
from apps.cart.services import get_or_create_cart
from apps.core.constants import BUYER_PROTECTION_WINDOW_HOURS, REFUND_PROCESSING_DELAY_MINUTES
from apps.core.enums import DeliveryMethod, RefundReasonCategory, RefundStatus
from apps.core.exceptions import ValidationFailedError

from .forms import CheckoutForm
from .models import Order, OrderItem, Refund
from .services import build_order_tracking, create_order_from_cart, request_refund
from .services.checkout import build_checkout_summary, validate_cart_stock

# Spec section 25's full happy-path timeline, in order. A digital item
# skips RETURN_IN_PROGRESS/ITEM_RECEIVED/SELLER_CONDITION_CONFIRMED
# entirely (see Refund.requires_physical_return) - the template dims
# those three steps rather than removing them, so the shape stays
# consistent between physical and digital items.
REFUND_TIMELINE_STATUSES = [
    RefundStatus.REQUESTED,
    RefundStatus.UNDER_REVIEW,
    RefundStatus.RETURN_IN_PROGRESS,
    RefundStatus.ITEM_RECEIVED,
    RefundStatus.SELLER_CONDITION_CONFIRMED,
    RefundStatus.PLATFORM_APPROVED,
    RefundStatus.PROCESSING,
    RefundStatus.PROCESSED,
]


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
        form = CheckoutForm(request.POST)

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

            return redirect("payments:initiate", order_reference=order.reference)
    else:
        initial = {
            "full_name": request.user.get_full_name() or request.user.username,
            "email": request.user.email,
        }
        form = CheckoutForm(initial=initial)

    return render(request, "orders/checkout.html", {
        "form": form,
        "cart": cart,
        # Server-computed from the start (spec section 19) - the JS below
        # only ever replaces this with another server response, never
        # computes a total itself.
        "summary": build_checkout_summary(
            cart, request.POST.get("delivery_method", DeliveryMethod.SHIPPING),
        ),
    })


@login_required(login_url='accounts:login')
def checkout_summary_view(request):
    """
    Spec section 19 - "before payment, request a server-generated
    checkout summary" / "never trust a browser-calculated final amount".

    Called by checkout.html's JS every time the delivery method radio
    changes. Every amount in the response is pre-formatted server-side
    (`_fmt` below) so the page does no money arithmetic of its own at
    all - not even the addition - only DOM text updates.
    """
    cart = get_or_create_cart(request)

    if not cart.items.exists():
        return JsonResponse({"error": "Your cart is empty."}, status=400)

    delivery_method = request.GET.get("delivery_method")
    if delivery_method not in DeliveryMethod.values:
        return JsonResponse({"error": "Invalid delivery method."}, status=400)

    def _fmt(amount):
        return f"₦{amount:,.2f}"

    summary = build_checkout_summary(cart, delivery_method)

    return JsonResponse({
        "sellers": [
            {
                "seller_name": group["seller_name"],
                "subtotal_display": _fmt(group["subtotal"]),
                "delivery_fee_display": _fmt(group["delivery_fee"]),
            }
            for group in summary["sellers"]
        ],
        "products_total_display": _fmt(summary["products_total"]),
        "total_delivery_display": _fmt(summary["total_delivery"]),
        "final_total_display": _fmt(summary["final_total"]),
    })


@login_required(login_url='accounts:login')
def order_list(request):
    orders = Order.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "orders/order_list.html", {"orders": orders})


@login_required(login_url='accounts:login')
def order_detail(request, reference):
    order = get_object_or_404(Order, reference=reference, user=request.user)

    delivery = getattr(order, "delivery", None)
    delivery_task = getattr(delivery, "delivery_task", None) if delivery else None
    delivered_at = delivery_task.delivered_at if delivery_task else None

    protection_deadline = None
    if delivered_at is not None:
        protection_deadline = delivered_at + timedelta(hours=BUYER_PROTECTION_WINDOW_HOURS)

    existing_refunds = Refund.objects.filter(order_item__order=order).select_related(
        "order_item",
    ).prefetch_related("evidence")

    return render(request, "orders/order_detail.html", {
        "order": order,
        # Spec section 20 - per-seller Confirmed/Picked Up + that
        # seller's own delivery fee (see apps.orders.services.tracking
        # for why the final delivery leg itself is shown once, shared,
        # rather than repeated per seller).
        "seller_tracking": build_order_tracking(order),
        # Spec section 21 - informational only; ISO timestamp handed to
        # the page's JS, which does the ticking. Never used to gate
        # anything - actual payout eligibility stays a backend/admin
        # decision (see apps.sellers.services.mark_seller_earning_available).
        "protection_deadline": protection_deadline.isoformat() if protection_deadline else None,
        "existing_refunds": existing_refunds,
        # Spec section 25 - dropdown options and the full 8-stage
        # timeline (REFUND_TIMELINE_STATUSES, below) so the template
        # doesn't hardcode either list.
        "reason_categories": RefundReasonCategory.choices,
        "refund_timeline_statuses": REFUND_TIMELINE_STATUSES,
        "REFUND_PROCESSING_DELAY_MINUTES": REFUND_PROCESSING_DELAY_MINUTES,
    })


@login_required(login_url='accounts:login')
def request_refund_view(request, reference, item_id):
    """
    Spec section 25's "Report issue"/"Request refund" form - item is
    fixed by the URL (one form per line item on the order detail page),
    reason_category is the dropdown, reason is the free-text
    explanation, and any uploaded files become RefundEvidence rows.
    """
    order = get_object_or_404(Order, reference=reference, user=request.user)
    item = get_object_or_404(OrderItem, pk=item_id, order=order)

    if request.method == "POST":
        reason = request.POST.get("reason", "").strip()
        reason_category = request.POST.get("reason_category", "")

        if reason_category not in RefundReasonCategory.values:
            messages.error(request, "Please choose a reason.")
        elif not reason:
            messages.error(request, "Please describe the issue before submitting.")
        else:
            try:
                request_refund(
                    order_item=item,
                    user=request.user,
                    reason=reason,
                    reason_category=reason_category,
                    evidence_files=request.FILES.getlist("evidence"),
                )
            except ValidationFailedError as e:
                messages.error(request, str(e))
            else:
                messages.success(request, "Your request has been submitted for review.")

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
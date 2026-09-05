import hashlib
import hmac
import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from apps.core.exceptions import ValidationFailedError
from apps.orders.models import Order

from .services import PaymentInitializationError, initialize_payment, verify_payment


@login_required(login_url='accounts:login')
def initiate_payment(request, order_reference):
    order = get_object_or_404(Order, reference=order_reference, user=request.user)

    if order.is_paid:
        return redirect("payments:success", order_reference=order.reference)

    callback_url = request.build_absolute_uri(reverse("payments:callback"))

    try:
        authorization_url = initialize_payment(order, callback_url)
    except PaymentInitializationError as e:
        messages.error(request, f"Could not start payment: {e}")
        return redirect("orders:order_detail", reference=order.reference)

    return redirect(authorization_url)


def payment_callback(request):
    """Paystack redirects the user's browser here after checkout."""
    reference = request.GET.get("reference")

    if not reference:
        messages.error(request, "No payment reference found.")
        return redirect("cart:cart_detail")

    try:
        payment, success = verify_payment(reference)
    except ValidationFailedError as e:
        messages.error(request, str(e))
        return redirect("cart:cart_detail")

    if success:
        return redirect("payments:success", order_reference=payment.order.reference)

    return redirect("payments:failed", order_reference=payment.order.reference)


def payment_success(request, order_reference):
    order = get_object_or_404(Order, reference=order_reference)
    return render(request, "payments/success.html", {"order": order})


def payment_failed(request, order_reference):
    order = get_object_or_404(Order, reference=order_reference)
    return render(request, "payments/failed.html", {"order": order})


@csrf_exempt
def paystack_webhook(request):
    """
    Server-to-server confirmation, independent of whether the user's
    browser made it back to payment_callback. Same signature-verification
    pattern as the legacy apps.views.paystack_webhook.
    """
    paystack_signature = request.headers.get("x-paystack-signature")

    if not paystack_signature:
        return HttpResponse(status=400)

    body = request.body
    secret = settings.PAYSTACK_SECRET_KEY.encode("utf-8")
    computed_signature = hmac.new(secret, body, hashlib.sha512).hexdigest()

    if not hmac.compare_digest(paystack_signature, computed_signature):
        return HttpResponse(status=401)

    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        return HttpResponse(status=400)

    event_type = event.get("event")

    if event_type == "charge.success":
        reference = event["data"]["reference"]
        try:
            verify_payment(reference)
        except ValidationFailedError:
            pass  # unknown reference - nothing to do

    elif event_type in ("transfer.success", "transfer.failed", "transfer.reversed"):
        _handle_transfer_event(event_type, event["data"])

    return HttpResponse(status=200)


def _handle_transfer_event(event_type, data):
    """
    Phase 10 - settles a seller/affiliate payout once Paystack confirms
    (or fails) the actual bank transfer. `data["reference"]` is the same
    value passed as `reference` to initiate_transfer - the payout's own
    reference (prefixed SPO-/APO- by apps.core.utils.generate_reference),
    so the prefix alone tells us which model to look in.
    """
    reference = data.get("reference", "")

    if reference.startswith("SPO-"):
        from apps.sellers.models import SellerPayout
        from apps.sellers.services import mark_seller_payout_failed, mark_seller_payout_paid

        payout = SellerPayout.objects.filter(reference=reference).first()
        if payout is None:
            return
        if event_type == "transfer.success":
            mark_seller_payout_paid(payout=payout)
        else:
            mark_seller_payout_failed(payout=payout, reason=f"Paystack {event_type}")

    elif reference.startswith("APO-"):
        from apps.affiliates.models import AffiliatePayout
        from apps.affiliates.services import mark_affiliate_payout_failed, mark_affiliate_payout_paid

        payout = AffiliatePayout.objects.filter(reference=reference).first()
        if payout is None:
            return
        if event_type == "transfer.success":
            mark_affiliate_payout_paid(payout=payout)
        else:
            mark_affiliate_payout_failed(payout=payout, reason=f"Paystack {event_type}")
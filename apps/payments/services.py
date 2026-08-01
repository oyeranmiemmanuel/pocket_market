"""
Paystack integration, per 15_PAYMENTS.md.

Same API call pattern as the legacy apps/views.py buy_now/checkout flow
(initialize -> redirect to authorization_url -> verify on callback/webhook),
generalized to work against a multi-item orders.Order instead of a single
Product.
"""

from decimal import Decimal

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.cart.services import get_or_create_cart
from apps.core.exceptions import ValidationFailedError
from apps.core.utils import generate_reference
from apps.delivery.services import create_delivery
from apps.orders.models import Order, OrderStatus

from .models import Payment, PaymentStatus

PAYSTACK_INITIALIZE_URL = "https://api.paystack.co/transaction/initialize"
PAYSTACK_VERIFY_URL = "https://api.paystack.co/transaction/verify/{reference}"


class PaymentInitializationError(ValidationFailedError):
    pass


def initialize_payment(order: Order, callback_url: str) -> str:
    """
    Create a Payment row and start a Paystack transaction for it.
    Returns the authorization_url to redirect the user to.
    """
    payment = Payment.objects.create(
        order=order,
        reference=generate_reference("PAY"),
        amount=order.total,
        status=PaymentStatus.PENDING,
    )

    headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
    data = {
        "email": order.email,
        "amount": int(order.total * 100),  # kobo
        "reference": payment.reference,
        "callback_url": callback_url,
        "metadata": {
            "order_reference": order.reference,
            "payment_reference": payment.reference,
        },
    }

    response = requests.post(PAYSTACK_INITIALIZE_URL, json=data, headers=headers, timeout=10)
    res_data = response.json()

    if not res_data.get("status"):
        payment.status = PaymentStatus.FAILED
        payment.save(update_fields=["status"])
        raise PaymentInitializationError(res_data.get("message", "Could not start payment."))

    return res_data["data"]["authorization_url"]


@transaction.atomic
def _finalize_successful_payment(payment: Payment):
    """
    Shared by both the callback and the webhook - written so calling it
    twice for the same payment (e.g. webhook arrives after the user's
    browser already hit the callback) is a safe no-op the second time.
    """
    if payment.status == PaymentStatus.SUCCESS:
        return  # already processed - idempotent

    payment.status = PaymentStatus.SUCCESS
    payment.paid_at = timezone.now()
    payment.save(update_fields=["status", "paid_at"])

    order = payment.order
    order.status = OrderStatus.PAID
    order.save(update_fields=["status"])

    # Kicks off tracking - which stage pipeline depends on order.delivery_method
    # (see apps.delivery.models: local delivery gets a shorter, faster-feeling
    # set of stages than shipping does).
    create_delivery(order, order.delivery_method)

    # Inventory: decrement stock now, not at order-creation time, so an
    # abandoned/unpaid order never holds stock hostage (16_INVENTORY.md).
    for item in order.items.select_related("product"):
        if item.product is not None:
            item.product.stock = max(0, item.product.stock - item.quantity)
            item.product.save(update_fields=["stock"])

    # Clear whichever cart this order's user currently has, if any.
    # hard_delete() - a soft-delete here would leave the items visible
    # via the default manager, since cart.items uses `objects` not `active`.
    if order.user is not None:
        cart = getattr(order.user, "cart", None)
        if cart is not None:
            cart.items.all().hard_delete()


def verify_payment(reference: str) -> tuple[Payment, bool]:
    """
    Verify a payment reference with Paystack and finalize it if
    successful. Returns (payment, success_bool). Safe to call more than
    once for the same reference.
    """
    try:
        payment = Payment.objects.select_related("order").get(reference=reference)
    except Payment.DoesNotExist:
        raise ValidationFailedError(f"No payment found for reference {reference}")

    if payment.status == PaymentStatus.SUCCESS:
        return payment, True  # already verified earlier - idempotent

    headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
    response = requests.get(PAYSTACK_VERIFY_URL.format(reference=reference), headers=headers, timeout=10)
    res_data = response.json()

    paystack_ok = res_data.get("status") and res_data.get("data", {}).get("status") == "success"

    if paystack_ok:
        payment.provider_reference = res_data["data"].get("reference", "")
        payment.save(update_fields=["provider_reference"])
        _finalize_successful_payment(payment)
        return payment, True

    payment.status = PaymentStatus.FAILED
    payment.save(update_fields=["status"])
    order = payment.order
    order.status = OrderStatus.FAILED
    order.save(update_fields=["status"])
    return payment, False

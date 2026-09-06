"""
Paystack integration, per 15_PAYMENTS.md.

Same API call pattern as the legacy apps/views.py buy_now/checkout flow
(initialize -> redirect to authorization_url -> verify on callback/webhook),
generalized to work against a multi-item orders.Order instead of a single
Product.
"""

from decimal import Decimal
from django.core.cache import cache
import requests
from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from apps.ledger.services import process_order_financials
from apps.cart.services import get_or_create_cart
from apps.core.exceptions import ValidationFailedError
from apps.core.utils import generate_reference
from apps.delivery.services import create_delivery
from apps.notifications.models import NotificationCategory
from apps.notifications.services import create_notification, notify_sellers_of_new_order
from apps.orders.models import Order, OrderStatus

from .models import Payment, PaymentStatus

PAYSTACK_INITIALIZE_URL = "https://api.paystack.co/transaction/initialize"
PAYSTACK_VERIFY_URL = "https://api.paystack.co/transaction/verify/{reference}"

PAYSTACK_BANK_LIST_URL = "https://api.paystack.co/bank"
PAYSTACK_RESOLVE_ACCOUNT_URL = "https://api.paystack.co/bank/resolve"
PAYSTACK_CREATE_RECIPIENT_URL = "https://api.paystack.co/transferrecipient"
PAYSTACK_INITIATE_TRANSFER_URL = "https://api.paystack.co/transfer"

BANK_LIST_CACHE_KEY = "paystack_bank_list_ngn"
BANK_LIST_CACHE_SECONDS = 60 * 60 * 24  # Paystack's bank list barely ever changes


class PaystackTransferError(ValidationFailedError):
    pass


def list_banks():
    """
    Phase 10 - Nigerian bank list + codes, needed to populate the bank
    dropdown on the seller/affiliate bank-details form. Paystack's
    Transfer Recipient API requires a bank_code, not a free-text bank
    name (spec section 22). Cached for a day - this list barely changes.
    """
    cached = cache.get(BANK_LIST_CACHE_KEY)
    if cached is not None:
        return cached

    headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
    response = requests.get(
        PAYSTACK_BANK_LIST_URL, params={"currency": "NGN"}, headers=headers, timeout=10,
    )
    res_data = response.json()

    if not res_data.get("status"):
        raise PaystackTransferError(res_data.get("message", "Could not load the bank list."))

    banks = [{"name": bank["name"], "code": bank["code"]} for bank in res_data["data"]]
    cache.set(BANK_LIST_CACHE_KEY, banks, BANK_LIST_CACHE_SECONDS)
    return banks


def resolve_bank_account(*, account_number, bank_code):
    """
    Spec section 22: "Validate: bank, account number, account name."
    Confirms the account exists and returns the account name exactly as
    the bank has it on file - callers use this name instead of trusting
    what the user typed, so a payout can never go to a mistyped account.
    """
    headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
    params = {"account_number": account_number, "bank_code": bank_code}
    response = requests.get(PAYSTACK_RESOLVE_ACCOUNT_URL, params=params, headers=headers, timeout=10)
    res_data = response.json()

    if not res_data.get("status"):
        raise PaystackTransferError(res_data.get("message", "Could not verify that account."))

    return {
        "account_name": res_data["data"]["account_name"],
        "account_number": res_data["data"]["account_number"],
    }


def create_transfer_recipient(*, name, account_number, bank_code):
    headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
    data = {
        "type": "nuban",
        "name": name,
        "account_number": account_number,
        "bank_code": bank_code,
        "currency": "NGN",
    }
    response = requests.post(PAYSTACK_CREATE_RECIPIENT_URL, json=data, headers=headers, timeout=10)
    res_data = response.json()

    if not res_data.get("status"):
        raise PaystackTransferError(res_data.get("message", "Could not register payout recipient."))

    return res_data["data"]["recipient_code"]


def initiate_transfer(*, recipient_code, amount, reference, reason):
    """
    `reference` should be the payout's own reference (SellerPayout.reference /
    AffiliatePayout.reference) - Paystack echoes it back in the
    transfer.success/transfer.failed webhook payload, which is how
    apps.payments.views.paystack_webhook knows which payout to settle.

    Note: unless your Paystack business account has asked support to
    disable OTP for API-initiated transfers, this call will come back
    with status "otp" rather than completing automatically - Paystack's
    normal behaviour for programmatic transfers.
    """
    headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
    data = {
        "source": "balance",
        "amount": int(amount * 100),  # kobo
        "recipient": recipient_code,
        "reference": reference,
        "reason": reason,
    }
    response = requests.post(PAYSTACK_INITIATE_TRANSFER_URL, json=data, headers=headers, timeout=10)
    res_data = response.json()

    if not res_data.get("status"):
        raise PaystackTransferError(res_data.get("message", "Could not initiate transfer."))

    return res_data["data"]

    
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

    # Phase 7/8 - commission calculation + financial ledger. Creates the
    # AffiliateCommission, SellerEarning, and LedgerEntry rows for every
    # eligible line item in one atomic step. No-ops cleanly per item
    # where there's no seller/no eligible affiliate - see
    # apps.ledger.services.process_order_financials's docstring. Runs
    # inside this same atomic block, and is itself idempotent, so calling
    # _finalize_successful_payment twice (callback + webhook both racing
    # to verify the same reference) never double-credits anyone or
    # double-writes the ledger (spec section 39).
    process_order_financials(order)

    # Clear whichever cart this order's user currently has, if any.
    # hard_delete() - a soft-delete here would leave the items visible
    # via the default manager, since cart.items uses `objects` not `active`.
    if order.user is not None:
        cart = getattr(order.user, "cart", None)
        if cart is not None:
            cart.items.all().hard_delete()

    # Inside the idempotency guard at the top of this function, so these
    # fire exactly once per order even though the callback and webhook
    # can both call this for the same payment.
    create_notification(
        user=order.user,
        category=NotificationCategory.PAYMENT_SUCCESSFUL,
        message=f"Payment received for order {order.reference}.",
        url=reverse("orders:order_detail", args=[order.reference]),
    )
    notify_sellers_of_new_order(order)


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
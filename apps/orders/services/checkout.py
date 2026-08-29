"""
Order creation from a Cart, per 13_CHECKOUT.md / 14_ORDERS.md.

Deliberately does NOT touch stock or clear the cart here - both only
happen once payment actually succeeds (see apps.payments.services), so an
abandoned/unpaid order never holds stock hostage.
"""

from decimal import Decimal

from django.db import transaction

from apps.core.constants import LOCAL_DELIVERY_FEE, SHIPPING_FEE
from apps.core.enums import DeliveryMethod
from apps.core.exceptions import ValidationFailedError
from apps.core.utils import generate_reference
from apps.sellers.services import resolve_commission_rate

from ..models import Order, OrderItem, ShippingAddress


class OutOfStockError(ValidationFailedError):
    """Raised when a cart item requests more than is currently in stock."""


def validate_cart_stock(cart):
    """
    Raise OutOfStockError with a clear message if anything in the cart
    exceeds available stock. Call before showing the checkout form too,
    not just at submission, so the user isn't surprised at the last step.
    """
    problems = []
    for item in cart.items.select_related("product"):
        if item.quantity > item.product.stock:
            problems.append(
                f"{item.product.name}: only {item.product.stock} left, "
                f"you have {item.quantity} in cart"
            )
    if problems:
        raise OutOfStockError("; ".join(problems))


def delivery_fee_for(method: str) -> Decimal:
    return Decimal(LOCAL_DELIVERY_FEE) if method == DeliveryMethod.LOCAL_DELIVERY else Decimal(SHIPPING_FEE)


@transaction.atomic
def create_order_from_cart(*, user, cart, email, full_name, phone, delivery_method, shipping_data):
    """
    Snapshot the cart into a real Order + OrderItems + ShippingAddress.

    Raises OutOfStockError if anything in the cart no longer fits
    available stock (checked again here, not just at form-render time -
    stock can change between viewing the form and submitting it).
    """
    if not cart.items.exists():
        raise ValidationFailedError("Cart is empty.")

    validate_cart_stock(cart)

    shipping_fee = delivery_fee_for(delivery_method)
    subtotal = sum((item.subtotal for item in cart.items.all()), Decimal("0"))
    total = subtotal + shipping_fee

    order = Order.objects.create(
        user=user,
        reference=generate_reference("ORD"),
        email=email,
        full_name=full_name,
        phone=phone,
        delivery_method=delivery_method,
        subtotal=subtotal,
        shipping_fee=shipping_fee,
        total=total,
    )

    for item in cart.items.select_related("product", "product__seller"):
        # Snapshot seller ownership + commission rate at the moment of
        # purchase (per docs/28_DECISIONS.md's existing snapshot pattern
        # for product_name/unit_price) - one Order can span multiple
        # sellers, so ownership must live on the line item, and freezing
        # the rate here means a later change to the seller's/product's
        # commission never rewrites a past order's numbers.
        OrderItem.objects.create(
            order=order,
            product=item.product,
            product_name=item.product.name,
            unit_price=item.product.price,
            quantity=item.quantity,
            seller=item.product.seller,
            platform_commission_rate=resolve_commission_rate(item.product),
        )

    ShippingAddress.objects.create(order=order, **shipping_data)

    return order

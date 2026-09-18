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

from ..models import Order, OrderItem, OrderSellerDelivery, ShippingAddress


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


def group_cart_by_seller(cart):
    """
    Group cart items by seller (Marketplace Frontend Roadmap section 18 -
    "Buyer Multi-Seller Cart"). Returns an ordered list of dicts:
    {"seller": SellerProfile or None, "seller_name": str,
    "items": [CartItem, ...], "subtotal": Decimal}.

    seller=None is its own group ("This Store") for platform-owned
    products - see OrderItem.seller's docstring in ..models for the same
    null-means-platform-owned convention on the order side.

    Group order is "first seller encountered in the cart", so the same
    buyer sees a stable, consistent seller order across the cart page,
    the checkout summary, and the eventual order confirmation - nothing
    here re-sorts alphabetically or by anything that could reshuffle
    between calls.
    """
    groups = {}
    order_of_sellers = []
    for item in cart.items.select_related("product", "product__seller"):
        seller = item.product.seller
        key = seller.id if seller else None
        if key not in groups:
            groups[key] = {
                "seller": seller,
                "seller_name": seller.store_name if seller else "This Store",
                "items": [],
                "subtotal": Decimal("0"),
            }
            order_of_sellers.append(key)
        groups[key]["items"].append(item)
        groups[key]["subtotal"] += item.subtotal
    return [groups[key] for key in order_of_sellers]


def build_checkout_summary(cart, delivery_method):
    """
    THE single source of truth for what a buyer owes, grouped by seller
    (Marketplace Frontend Roadmap sections 18/19). The cart page's
    (estimated) breakdown, the checkout page's live AJAX summary, and the
    actual Order/OrderSellerDelivery rows created by
    create_order_from_cart below all go through this same function - so
    the number a buyer is shown is never allowed to drift from the
    number they're actually charged.

    Pure / no side effects - callers decide what to do with the result.
    Each seller present in the cart is charged delivery_fee_for(method)
    once for their whole slice of the order, however many items or units
    it contains - one seller, one delivery run, one fee.
    """
    fee_per_seller = delivery_fee_for(delivery_method)
    groups = group_cart_by_seller(cart)

    seller_breakdown = []
    total_delivery_fee = Decimal("0")
    products_total = Decimal("0")

    for group in groups:
        seller_breakdown.append({
            "seller_id": group["seller"].id if group["seller"] else None,
            "seller_name": group["seller_name"],
            "subtotal": group["subtotal"],
            "delivery_fee": fee_per_seller,
            "item_count": len(group["items"]),
        })
        total_delivery_fee += fee_per_seller
        products_total += group["subtotal"]

    return {
        "delivery_method": delivery_method,
        "sellers": seller_breakdown,
        "products_total": products_total,
        "total_delivery_fee": total_delivery_fee,
        "final_total": products_total + total_delivery_fee,
    }


@transaction.atomic
def create_order_from_cart(*, user, cart, email, full_name, phone, delivery_method, shipping_data, affiliate=None):
    """
    Snapshot the cart into a real Order + OrderItems + OrderSellerDelivery
    rows + ShippingAddress.

    Raises OutOfStockError if anything in the cart no longer fits
    available stock (checked again here, not just at form-render time -
    stock can change between viewing the form and submitting it).

    `affiliate` (Phase 7) is whichever AffiliateProfile the attribution
    cookie currently points to - resolved by the caller (the checkout
    view has the request; this service function deliberately doesn't take
    a request, per the existing separation between views and services).
    Snapshotted onto the order now, once, rather than re-resolved from the
    cookie later at payment time, so a cookie that later expires or an
    affiliate who's later suspended never changes which order they were
    credited for. Self-referral (spec section 43) is guarded here too,
    not only at click-tracking time - guest browsing under a referral link
    and then logging into/creating *that same* affiliate's own account
    before checkout out must never earn them a commission on themselves.
    """
    if not cart.items.exists():
        raise ValidationFailedError("Cart is empty.")

    validate_cart_stock(cart)

    if affiliate is not None and user is not None and affiliate.user_id == user.id:
        affiliate = None

    # The exact same function the buyer's cart page and checkout page
    # summaries were built from - the order's numbers can never end up
    # different from what the buyer was shown right before paying.
    summary = build_checkout_summary(cart, delivery_method)

    order = Order.objects.create(
        user=user,
        reference=generate_reference("ORD"),
        email=email,
        full_name=full_name,
        phone=phone,
        delivery_method=delivery_method,
        subtotal=summary["products_total"],
        shipping_fee=summary["total_delivery_fee"],
        total=summary["final_total"],
        affiliate=affiliate,
        affiliate_code=affiliate.affiliate_code if affiliate else "",
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

    for seller_row in summary["sellers"]:
        OrderSellerDelivery.objects.create(
            order=order,
            seller_id=seller_row["seller_id"],
            delivery_fee=seller_row["delivery_fee"],
        )

    ShippingAddress.objects.create(order=order, **shipping_data)

    return order
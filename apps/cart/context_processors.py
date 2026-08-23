"""
Makes cart data available in every template (for the nav cart icon)
without forcing a Cart/session to be created for visitors who've never
touched the cart - only reads one if it already exists.
"""

from .models import Cart


def cart_context(request):
    cart = None

    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user).first()
    elif request.session.session_key:
        cart = Cart.objects.filter(session_key=request.session.session_key).first()

    if cart:
        items = list(cart.items.select_related("product").all())
        count = sum(item.quantity for item in items)
        total = cart.total_price
    else:
        items = []
        count = 0
        total = 0

    return {
        "nav_cart_items": items,
        "nav_cart_count": count,
        "nav_cart_total": total,
    }

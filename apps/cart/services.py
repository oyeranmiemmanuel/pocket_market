"""
Shared cart logic - used by both apps.cart's own views and apps.orders'
checkout view (which needs to read the current cart to build an Order
from it).
"""

from .models import Cart


def get_or_create_cart(request):
    """
    Logged in -> one cart per user.
    Anonymous  -> one cart per session (session key created if missing).
    """
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart

    if not request.session.session_key:
        request.session.save()

    cart, _ = Cart.objects.get_or_create(session_key=request.session.session_key)
    return cart

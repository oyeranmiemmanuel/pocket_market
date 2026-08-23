"""
Shared cart logic - used by both apps.cart's own views and apps.orders'
checkout view (which needs to read the current cart to build an Order
from it), and apps.catalog's product_detail Add to Cart form.
"""

from django.http import JsonResponse

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


def is_ajax_request(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def merge_guest_cart_into_user(request, user):
    """
    Fold a guest (session-based) cart into the logging-in user's cart.

    Must be called BEFORE django.contrib.auth.login() - login() cycles
    the session key for security, so the guest cart's session_key would
    no longer match anything afterward. Existing quantities are added
    together per product rather than overwritten, in case the user
    already had items in their own account's cart from a previous visit.
    """
    session_key = request.session.session_key
    if not session_key:
        return

    guest_cart = Cart.objects.filter(session_key=session_key, user__isnull=True).first()
    if not guest_cart or not guest_cart.items.exists():
        return

    user_cart, _ = Cart.objects.get_or_create(user=user)

    for item in guest_cart.items.select_related("product").all():
        existing = user_cart.items.filter(product=item.product).first()
        if existing:
            existing.quantity += item.quantity
            existing.save(update_fields=["quantity"])
        else:
            item.cart = user_cart
            item.save(update_fields=["cart"])

    # Hard delete, not the default soft-delete - this row has served its
    # purpose and session_key is unique, no reason to keep it around.
    guest_cart.delete(hard=True)


def cart_json_response(cart, message=""):
    """
    Shared JSON shape for the nav cart popup - every action that touches
    the cart (add/update/remove, from any app) returns this same shape
    so the frontend can update the icon/popup without a page reload.
    """
    items = [
        {
            "item_id": str(item.id),
            "product_name": item.product.name,
            "quantity": item.quantity,
            "unit_price": str(item.product.price),
            "subtotal": str(item.subtotal),
            "image_url": item.product.image.url if item.product.image else "",
        }
        for item in cart.items.select_related("product").all()
    ]
    return JsonResponse({
        "message": message,
        "count": cart.total_items,
        "total": str(cart.total_price),
        "items": items,
    })

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.catalog.models import Product

from .models import CartItem
from .services import get_or_create_cart


def cart_detail(request):
    cart = get_or_create_cart(request)
    return render(request, "cart/cart_detail.html", {"cart": cart})


def add_to_cart(request, product_id):
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    cart = get_or_create_cart(request)

    item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={"quantity": 1},
    )

    if not created:
        item.quantity += 1
        item.save()

    messages.success(request, f"{product.name} added to cart.")
    return redirect("cart:cart_detail")


def update_cart_item(request, item_id):
    cart = get_or_create_cart(request)
    item = get_object_or_404(CartItem, pk=item_id, cart=cart)

    if request.method == "POST":
        try:
            quantity = int(request.POST.get("quantity", 1))
        except ValueError:
            quantity = 1

        if quantity < 1:
            item.delete()
            messages.info(request, "Item removed from cart.")
        else:
            item.quantity = quantity
            item.save()
            messages.success(request, "Cart updated.")

    return redirect("cart:cart_detail")


def remove_from_cart(request, item_id):
    cart = get_or_create_cart(request)
    item = get_object_or_404(CartItem, pk=item_id, cart=cart)
    item.delete()
    messages.info(request, "Item removed from cart.")
    return redirect("cart:cart_detail")

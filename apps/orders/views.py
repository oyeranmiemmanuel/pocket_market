from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.cart.services import get_or_create_cart
from apps.core.exceptions import ValidationFailedError

from .forms import CheckoutForm
from .models import Order, OrderItem
from .services import create_order_from_cart
from .services.checkout import validate_cart_stock


@login_required
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

    return render(request, "orders/checkout.html", {"form": form, "cart": cart})


@login_required
def order_list(request):
    orders = Order.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "orders/order_list.html", {"orders": orders})


@login_required
def order_detail(request, reference):
    order = get_object_or_404(Order, reference=reference, user=request.user)
    return render(request, "orders/order_detail.html", {"order": order})


@login_required
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

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.cart.models import CartItem
from apps.cart.services import get_or_create_cart

from .models import Category, Product


def product_list(request):
    """
    Real product browsing page - replaces the old monolith's shop() view.
    Supports an optional ?category=<slug> filter.
    """
    products = Product.active.filter(is_active=True).select_related("category")

    category_slug = request.GET.get("category")
    selected_category = None
    if category_slug:
        selected_category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=selected_category)

    return render(request, "catalog/product_list.html", {
        "products": products,
        "categories": Category.active.all(),
        "selected_category": selected_category,
    })


def product_detail(request, slug):
    """Single product page - real 'Add to Cart' entry point."""
    product = get_object_or_404(Product.active, slug=slug, is_active=True)

    if request.method == "POST":
        try:
            quantity = max(1, int(request.POST.get("quantity", 1)))
        except ValueError:
            quantity = 1

        cart = get_or_create_cart(request)
        item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={"quantity": quantity},
        )
        if not created:
            item.quantity += quantity
            item.save()

        messages.success(request, f"{product.name} added to cart.")
        return redirect("cart:cart_detail")

    related_products = (
        Product.active.filter(is_active=True, category=product.category)
        .exclude(pk=product.pk)[:4]
        if product.category else []
    )

    return render(request, "catalog/product_detail.html", {
        "product": product,
        "related_products": related_products,
    })

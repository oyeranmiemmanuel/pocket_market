from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.cart.models import CartItem
from apps.cart.services import cart_json_response, get_or_create_cart, is_ajax_request

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


RECENTLY_VIEWED_SESSION_KEY = "recently_viewed_products"
RECENTLY_VIEWED_MAX = 8


def _track_recently_viewed(request, product):
    """Keep a session-stored list of recently viewed product slugs, most recent first."""
    viewed = request.session.get(RECENTLY_VIEWED_SESSION_KEY, [])
    viewed = [slug for slug in viewed if slug != product.slug]
    viewed.insert(0, product.slug)
    request.session[RECENTLY_VIEWED_SESSION_KEY] = viewed[:RECENTLY_VIEWED_MAX]


def product_detail(request, slug):
    """Single product page - real 'Add to Cart' entry point."""
    product = get_object_or_404(
        Product.active.select_related("seller").prefetch_related(
            "gallery_images", "color_variants", "size_variants"
        ),
        slug=slug, is_active=True,
    )
    _track_recently_viewed(request, product)

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

        message = f"{product.name} added to cart."

        if is_ajax_request(request):
            return cart_json_response(cart, message)

        messages.success(request, message)
        return redirect("cart:cart_detail")

    related_products = (
        Product.active.filter(is_active=True, category=product.category)
        .exclude(pk=product.pk)[:4]
        if product.category else []
    )

    viewed_slugs = [
        slug for slug in request.session.get(RECENTLY_VIEWED_SESSION_KEY, [])
        if slug != product.slug
    ]
    recently_viewed = []
    if viewed_slugs:
        products_by_slug = Product.active.in_bulk(viewed_slugs, field_name="slug")
        recently_viewed = [
            products_by_slug[slug] for slug in viewed_slugs if slug in products_by_slug
        ]

    return render(request, "catalog/product_detail.html", {
        "product": product,
        "related_products": related_products,
        "recently_viewed": recently_viewed,
    })

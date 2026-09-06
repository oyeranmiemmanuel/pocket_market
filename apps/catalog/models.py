from django.conf import settings
from django.db import models

from apps.core.models import BaseModel
from apps.core.utils import unique_slugify


class Category(BaseModel):
    """Product grouping (e.g. Clothing, Digital Downloads)."""

    name = models.CharField(max_length=150, unique=True)

    slug = models.SlugField(max_length=170, unique=True, blank=True)

    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, self.name)
        super().save(*args, **kwargs)


class Product(BaseModel):
    """
    Moved here from the old monolith (apps/models.py) per
    ARCHITECTURE.MD - catalog owns products/categories.
    """

    PRODUCT_TYPES = (
        ('digital', 'Digital Product'),
        ('physical', 'Physical Product'),
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )

    seller = models.ForeignKey(
        "sellers.SellerProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
        help_text="Null = platform-owned product (100% of the sale goes "
                   "to the platform, no seller earnings are created).",
    )

    # Per-product override of the seller's own commission_rate, which
    # itself overrides the platform default. Null = fall through to
    # whichever the next level up specifies.
    commission_rate = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
    )

    # Phase 7 - affiliate commission hierarchy (spec section 16):
    # Product.affiliate_commission_rate -> Seller.affiliate_commission_rate
    # -> PLATFORM_AFFILIATE_COMMISSION_RATE_DEFAULT. Deliberately a
    # separate field from `commission_rate` above - that one is the
    # platform's own cut from the seller, this one is what an affiliate
    # earns for referring a sale of *this* product. See
    # apps.affiliates.services.resolve_affiliate_commission_rate.
    affiliate_commission_rate = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Affiliate commission percentage for this specific "
                   "product. Leave blank to fall through to the seller's "
                   "rate, then the platform default.",
    )

    name = models.CharField(max_length=200)

    slug = models.SlugField(max_length=220, unique=True, blank=True)

    description = models.TextField()

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    image = models.ImageField(
        upload_to='products/',
        blank=True,
        null=True
    )

    product_type = models.CharField(
        max_length=10,
        choices=PRODUCT_TYPES,
        default='physical'
    )

    digital_file = models.FileField(
        upload_to='digital_products/',
        blank=True,
        null=True
    )

    stock = models.PositiveIntegerField(
        default=0,
        help_text="Number of items available"
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether this product is visible/purchasable. "
                   "Separate from soft-delete (deleted_at).",
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def is_digital(self):
        return self.product_type == 'digital'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, self.name)
        super().save(*args, **kwargs)


class ProductImage(BaseModel):
    """
    Extra gallery images for a product, on top of Product.image (which
    stays as the primary/thumbnail image used in listings). A product
    can have up to MAX_IMAGES of these - enforced in the seller product
    form, not at the database level, so existing data is never at risk
    of violating a hard constraint.
    """

    MAX_IMAGES = 8

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="gallery_images",
    )

    image = models.ImageField(upload_to="products/gallery/")

    alt_text = models.CharField(max_length=200, blank=True)

    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "created_at"]

    def __str__(self):
        return f"Image for {self.product.name}"


class ProductColorVariant(BaseModel):
    """
    A selectable color option shown on the product detail page.

    Presentational only for now: selecting a color doesn't change price,
    doesn't have its own stock count, and isn't recorded on the cart/order
    (CartItem/OrderItem still reference Product directly, not a variant).
    Wiring color/size into actual per-variant stock and order history is a
    larger change across cart+orders and is intentionally out of scope
    here - see conversation notes.
    """

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="color_variants",
    )

    name = models.CharField(max_length=50)

    hex_code = models.CharField(
        max_length=7,
        blank=True,
        help_text="e.g. #1D4ED8 - used to render the swatch color.",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.product.name})"


class ProductSizeVariant(BaseModel):
    """
    A selectable size option shown on the product detail page.
    Presentational only - see ProductColorVariant docstring.
    """

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="size_variants",
    )

    label = models.CharField(max_length=20)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.label} ({self.product.name})"


class Review(BaseModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.product} - {self.rating}★"
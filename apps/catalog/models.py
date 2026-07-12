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

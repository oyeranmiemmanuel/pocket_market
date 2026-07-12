from django.conf import settings
from django.db import models

from apps.catalog.models import Product
from apps.core.models import BaseModel


class Cart(BaseModel):
    """
    One cart per logged-in user, or one per anonymous session.

    Site currently requires login for most flows, but this supports
    guest carts too (session_key) so that isn't a hard requirement
    going forward.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="cart",
    )

    session_key = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        unique=True,
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(user__isnull=False) | models.Q(session_key__isnull=False),
                name="cart_has_user_or_session",
            ),
        ]

    def __str__(self):
        return f"Cart ({self.user or self.session_key})"

    @property
    def total_items(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def total_price(self):
        return sum(item.subtotal for item in self.items.all())


class CartItem(BaseModel):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="cart_items",
    )

    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ("cart", "product")

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

    @property
    def subtotal(self):
        return self.product.price * self.quantity

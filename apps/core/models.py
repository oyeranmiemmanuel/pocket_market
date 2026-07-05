from django.db import models

from .managers import ActiveManager


class BaseModel(models.Model):
    """
    Base model inherited by all project models.
    """

    created_at = models.DateTimeField(
        auto_now_add=True,
        editable=False,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    objects = models.Manager()

    active = ActiveManager()

    class Meta:
        abstract = True
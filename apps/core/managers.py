from django.db import models



class ActiveQuerySet(models.QuerySet):
    """QuerySet with soft-delete-aware helpers."""

    def active(self):
        return self.filter(is_active=True)

    def inactive(self):
        return self.filter(is_active=False)



class ActiveManager(models.Manager):
    """
    Returns only active records.
    """

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class InactiveManager(models.Manager):
    """
    Returns only inactive records.
    """

    def get_queryset(self):
        return super().get_queryset().filter(is_active=False)
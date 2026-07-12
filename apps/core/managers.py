"""
Reusable model managers/querysets shared across apps.

Soft-delete policy (per docs/03_DATABASE.md): rows are never hard-deleted
by default. BaseModel.delete() sets `deleted_at` instead of removing the
row. Use `.hard_delete()` explicitly when you really mean to destroy data.
"""

from django.db import models
from django.utils import timezone


class ActiveQuerySet(models.QuerySet):
    """QuerySet with soft-delete-aware helpers."""

    def active(self):
        return self.filter(deleted_at__isnull=True)

    def deleted(self):
        return self.filter(deleted_at__isnull=False)

    def delete(self):
        """Bulk soft-delete: stamps deleted_at instead of removing rows."""
        return self.update(deleted_at=timezone.now())

    def hard_delete(self):
        """Bulk hard-delete: actually removes rows. Use deliberately."""
        return super().delete()


class ActiveManager(models.Manager.from_queryset(ActiveQuerySet)):
    """Manager that only returns rows where deleted_at IS NULL."""

    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)

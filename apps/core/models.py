import uuid

from django.db import models
from django.utils import timezone

from .managers import ActiveManager, ActiveQuerySet


class BaseModel(models.Model):
    """
    Abstract base model for all models.

    Per docs/06_UUID_POLICY.md and docs/03_DATABASE.md:
    - UUID primary keys everywhere, never expose integer IDs
    - soft delete via deleted_at, not a boolean flag
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    deleted_at = models.DateTimeField(null=True, blank=True)

    # Default manager: sees every row, including soft-deleted ones.
    objects = models.Manager.from_queryset(ActiveQuerySet)()

    # Only rows where deleted_at IS NULL.
    active = ActiveManager()

    class Meta:
        abstract = True

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def delete(self, using=None, keep_parents=False, hard=False):
        """
        Soft-delete by default (stamps deleted_at). Pass hard=True to
        actually remove the row.
        """
        if hard:
            return super().delete(using=using, keep_parents=keep_parents)

        self.deleted_at = timezone.now()
        self.save(using=using, update_fields=["deleted_at"])

    def restore(self):
        self.deleted_at = None
        self.save(update_fields=["deleted_at"])

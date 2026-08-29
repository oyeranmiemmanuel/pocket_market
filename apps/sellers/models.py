from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class SellerStatus(models.TextChoices):
    PENDING = "pending", "Pending Review"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    SUSPENDED = "suspended", "Suspended"


class SellerProfile(BaseModel):
    """
    A seller is a CUSTOMER account with an approved store attached, not a
    separate account type - a user can be a customer, a seller, and an
    affiliate all at once. Access to seller features is gated on
    status == APPROVED, not on User.role (see apps.sellers.permissions).
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="seller_profile",
    )

    store_name = models.CharField(max_length=150)

    store_slug = models.SlugField(max_length=170, unique=True, blank=True)

    store_description = models.TextField(blank=True)

    logo = models.ImageField(upload_to="sellers/logos/", blank=True, null=True)

    banner = models.ImageField(upload_to="sellers/banners/", blank=True, null=True)

    phone = models.CharField(max_length=20)

    business_email = models.EmailField()

    status = models.CharField(
        max_length=20,
        choices=SellerStatus.choices,
        default=SellerStatus.PENDING,
    )

    rejection_reason = models.TextField(blank=True)

    # Per-seller override of the platform default (core.constants).
    # Null = use the platform default rate.
    commission_rate = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Percentage platform takes from this seller's sales. "
                   "Leave blank to use the platform default.",
    )

    bank_name = models.CharField(max_length=100, blank=True)
    bank_account_number = models.CharField(max_length=20, blank=True)
    bank_account_name = models.CharField(max_length=150, blank=True)

    reviewed_at = models.DateTimeField(null=True, blank=True)

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="seller_reviews",
    )

    class Meta:
        db_table = "seller_profiles"
        verbose_name = "Seller Profile"
        verbose_name_plural = "Seller Profiles"

    def __str__(self):
        return f"{self.store_name} ({self.get_status_display()})"

    @property
    def is_approved(self):
        return self.status == SellerStatus.APPROVED

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class RiderStatus(models.TextChoices):
    """
    Mirrors SellerStatus/AffiliateStatus's collapsed scheme (spec section
    5 lists DRAFT/SUBMITTED/UNDER_REVIEW/APPROVED/REJECTED/SUSPENDED-style
    granularity in the abstract, but SellerStatus/AffiliateStatus already
    collapsed that down to PENDING for everything pre-approval - same
    move here for consistency). INACTIVE is distinct from SUSPENDED: a
    rider can voluntarily go INACTIVE (pause themselves) and come back,
    while SUSPENDED is an admin action.
    """

    PENDING = "pending", "Pending Review"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    SUSPENDED = "suspended", "Suspended"
    INACTIVE = "inactive", "Inactive"


class RiderVehicleType(models.TextChoices):
    BICYCLE = "bicycle", "Bicycle"
    MOTORCYCLE = "motorcycle", "Motorcycle"
    CAR = "car", "Car"
    VAN = "van", "Van"
    ON_FOOT = "on_foot", "On Foot"


class RiderProfile(BaseModel):
    """
    Like SellerProfile/AffiliateProfile, this is a capability attached to
    a CUSTOMER account, not a separate account type - a user can be a
    customer, seller, affiliate, and rider all at once. Access gated on
    status == APPROVED (and, for actually receiving assignments,
    is_available too), never on User.role - same reasoning as
    apps.sellers.permissions/apps.affiliates.permissions.

    Phase 1 scope only (spec section 5): profile + application + admin
    approval. Rider assignment, delivery state machine, and secure
    delivery confirmation (spec sections 15-17) are later phases.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="rider_profile",
    )

    full_name = models.CharField(max_length=150)

    phone = models.CharField(max_length=20)

    contact_email = models.EmailField(
        blank=True,
        help_text="Optional - defaults to the account email if left blank.",
    )

    service_area = models.CharField(
        max_length=150,
        help_text="Area/zone this rider delivers in, e.g. 'Ibadan North, Oyo State'.",
    )

    vehicle_type = models.CharField(
        max_length=20,
        choices=RiderVehicleType.choices,
        default=RiderVehicleType.MOTORCYCLE,
    )

    status = models.CharField(
        max_length=20,
        choices=RiderStatus.choices,
        default=RiderStatus.PENDING,
    )

    rejection_reason = models.TextField(blank=True)

    # Spec section 5 separates "Verification status" from "Account
    # status" - this is identity/document verification (admin-controlled,
    # e.g. after checking a license/ID), independent of application
    # approval itself.
    verified = models.BooleanField(default=False)

    # Rider-controlled "on shift" toggle - short-term, unlike `status`
    # which is the account's standing. Only meaningful once APPROVED.
    is_available = models.BooleanField(default=False)

    # Payout information (spec section 5) - same shape as
    # SellerProfile/AffiliateProfile bank fields, protected the same way
    # (never returned through ordinary public APIs).
    bank_code = models.CharField(max_length=10, blank=True)
    bank_name = models.CharField(max_length=100, blank=True)
    bank_account_number = models.CharField(max_length=20, blank=True)
    bank_account_name = models.CharField(max_length=150, blank=True)

    reviewed_at = models.DateTimeField(null=True, blank=True)

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rider_reviews",
    )

    class Meta:
        db_table = "rider_profiles"
        verbose_name = "Rider Profile"
        verbose_name_plural = "Rider Profiles"

    def __str__(self):
        return f"{self.full_name} ({self.get_status_display()})"

    @property
    def is_approved(self):
        return self.status == RiderStatus.APPROVED

    @property
    def can_receive_assignments(self):
        """
        Gate used by later phases (spec section 15) - approved, not
        suspended/inactive, and currently toggled available.
        """
        return self.status == RiderStatus.APPROVED and self.is_available
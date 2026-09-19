from decimal import Decimal

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

    # ------------------------------------------------------------------
    # Spec sections 13/16/22-24 - balances aggregated straight from
    # RiderEarning rows, mirroring SellerProfile/AffiliateProfile's own
    # earnings properties exactly. No RiderPayout model exists yet, so
    # unlike withdrawable_balance on those two, available_earnings here
    # isn't reduced by any in-flight payout reservation.
    # ------------------------------------------------------------------

    def _earning_sum(self, *statuses):
        return self.earnings.filter(status__in=statuses).aggregate(
            total=models.Sum("amount")
        )["total"] or Decimal("0.00")

    @property
    def total_earnings(self):
        return self._earning_sum(
            RiderEarningStatus.PENDING, RiderEarningStatus.CONFIRMED,
            RiderEarningStatus.AVAILABLE, RiderEarningStatus.PAID,
        )

    @property
    def pending_earnings(self):
        return self._earning_sum(RiderEarningStatus.PENDING, RiderEarningStatus.CONFIRMED)

    @property
    def pending_only_earnings(self):
        return self._earning_sum(RiderEarningStatus.PENDING)

    @property
    def held_earnings(self):
        return self._earning_sum(RiderEarningStatus.CONFIRMED)

    @property
    def available_earnings(self):
        return self._earning_sum(RiderEarningStatus.AVAILABLE)

    @property
    def paid_earnings(self):
        return self._earning_sum(RiderEarningStatus.PAID)


class RiderEarningStatus(models.TextChoices):
    """Mirrors apps.sellers.models.EarningStatus / apps.affiliates.models.CommissionStatus's lifecycle exactly."""

    PENDING = "pending", "Pending"
    CONFIRMED = "confirmed", "Held"
    AVAILABLE = "available", "Available"
    PAID = "paid", "Withdrawn"
    CANCELLED = "cancelled", "Cancelled"
    REVERSED = "reversed", "Reversed"


class RiderEarning(BaseModel):
    """
    Spec sections 16/24 - what a rider earns for completing one leg of
    a delivery. One row per completed PickupTask (collecting a seller's
    package) or DeliveryTask (the final leg to the buyer) - never both
    on the same row, since they're separately dispatched and can go to
    different riders. Created once, at the moment
    apps.logistics.services.mark_package_collected /
    mark_delivery_task_delivered actually completes that leg - never
    computed live in a view, mirroring how SellerEarning/
    AffiliateCommission are created once at payment-success time.

    No automated hold-release timer exists yet, same as
    SellerEarning/AffiliateCommission - PENDING -> CONFIRMED ("Held") ->
    AVAILABLE -> PAID ("Withdrawn") is a manual admin step for now (see
    apps.riders.admin).
    """

    rider = models.ForeignKey(
        "riders.RiderProfile", on_delete=models.PROTECT, related_name="earnings",
        help_text="PROTECT, not SET_NULL/CASCADE - an earning must never lose track of who it's owed to.",
    )

    order = models.ForeignKey("orders.Order", on_delete=models.PROTECT, related_name="rider_earnings")

    pickup_task = models.ForeignKey(
        "logistics.PickupTask", on_delete=models.PROTECT, null=True, blank=True, related_name="rider_earning",
    )
    delivery_task = models.ForeignKey(
        "logistics.DeliveryTask", on_delete=models.PROTECT, null=True, blank=True, related_name="rider_earning",
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)

    status = models.CharField(max_length=20, choices=RiderEarningStatus.choices, default=RiderEarningStatus.PENDING)

    confirmed_at = models.DateTimeField(null=True, blank=True)

    reversal_of = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="reversals",
        help_text="Set only on a reversal row - points back at the original earning it cancels out.",
    )

    class Meta:
        db_table = "rider_earnings"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["rider", "status"])]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(pickup_task__isnull=False, delivery_task__isnull=True)
                    | models.Q(pickup_task__isnull=True, delivery_task__isnull=False)
                ),
                name="rider_earning_exactly_one_task",
            ),
            models.UniqueConstraint(
                fields=["pickup_task"],
                condition=models.Q(reversal_of__isnull=True, pickup_task__isnull=False),
                name="unique_original_earning_per_pickup_task",
            ),
            models.UniqueConstraint(
                fields=["delivery_task"],
                condition=models.Q(reversal_of__isnull=True, delivery_task__isnull=False),
                name="unique_original_earning_per_delivery_task",
            ),
        ]

    def __str__(self):
        return f"{self.rider.full_name} earns {self.amount} on {self.order.reference} ({self.get_status_display()})"

    @property
    def leg(self):
        return "pickup" if self.pickup_task_id else "delivery"
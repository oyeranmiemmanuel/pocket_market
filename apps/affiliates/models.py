from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.core.models import BaseModel


class AffiliateStatus(models.TextChoices):
    PENDING = "pending", "Pending Review"
    ACTIVE = "active", "Active"
    REJECTED = "rejected", "Rejected"
    SUSPENDED = "suspended", "Suspended"


class AffiliateProfile(BaseModel):
    """
    Like SellerProfile, this is a capability attached to a CUSTOMER
    account, not a separate account type - a user can be a customer,
    seller, and affiliate all at once. Access gated on
    status == ACTIVE (see apps.affiliates.permissions), never on
    User.role.

    Phase 5 scope only: profile + application + admin approval.
    Referral tracking (AffiliateLink/AffiliateClick) and commission
    calculation on purchase are explicitly out of scope here - later
    phases, per docs/28_DECISIONS.md.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="affiliate_profile",
    )

    affiliate_code = models.CharField(max_length=20, unique=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=AffiliateStatus.choices,
        default=AffiliateStatus.PENDING,
    )

    rejection_reason = models.TextField(blank=True)

    commission_rate = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Percentage of a referred sale paid to this affiliate. "
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
        related_name="affiliate_reviews",
    )

    class Meta:
        db_table = "affiliate_profiles"
        verbose_name = "Affiliate Profile"
        verbose_name_plural = "Affiliate Profiles"

    def __str__(self):
        return f"{self.affiliate_code or self.user} ({self.get_status_display()})"

    @property
    def is_active(self):
        return self.status == AffiliateStatus.ACTIVE

    @property
    def total_clicks(self):
        return self.clicks.count()

    @property
    def total_conversions(self):
        """Always 0 until Phase 7 wires up commission/conversion tracking - computed honestly, not hard-coded."""
        return self.clicks.filter(converted=True).count()


class AffiliateLink(BaseModel):
    """
    A ready-to-share referral link for one (affiliate, product) pair -
    e.g. "generate a link for Nike Sneakers" from the affiliate's
    dashboard. `referral_code` mirrors `affiliate.affiliate_code` at
    creation time - all links from one affiliate currently share the same
    code (?ref=<code> identifies the affiliate; the product itself comes
    from the URL path, e.g. /products/nike-sneakers/?ref=EMMA123), but
    keeping it as its own field leaves room for true per-link codes later
    without a schema change.
    """

    affiliate = models.ForeignKey(
        AffiliateProfile,
        on_delete=models.CASCADE,
        related_name="links",
    )

    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="affiliate_links",
    )

    referral_code = models.CharField(max_length=20, editable=False)

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "affiliate_links"
        unique_together = ("affiliate", "product")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.referral_code} -> {self.product.name}"

    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = self.affiliate.affiliate_code
        super().save(*args, **kwargs)

    @property
    def target_url(self):
        """Relative URL only - combine with request.scheme/get_host in templates for a full copyable link."""
        return f"{reverse('catalog:product_detail', args=[self.product.slug])}?ref={self.referral_code}"

    @property
    def total_clicks(self):
        return self.clicks.count()


class AffiliateClick(BaseModel):
    """
    One recorded visit via ?ref=<code>. Deliberately does NOT store the
    visitor's IP address or any other identifying info (spec section 13:
    "Be careful with IP addresses and privacy... do not collect
    unnecessary personal information") - de-duplication uses the Django
    session key instead, which identifies a browser session, not a person.

    `converted` stays False here always - flipping it true on a
    successful attributed order is Phase 7 (commission calculation)
    territory, not this phase.
    """

    affiliate = models.ForeignKey(
        AffiliateProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clicks",
    )

    affiliate_link = models.ForeignKey(
        AffiliateLink,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clicks",
    )

    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="affiliate_clicks",
    )

    session_key = models.CharField(
        max_length=40,
        blank=True,
        help_text="Django session key of the visitor, used only to de-duplicate repeat clicks - not to identify a person.",
    )

    converted = models.BooleanField(
        default=False,
        help_text="Set True in a later phase once this click leads to a paid, attributed order.",
    )

    class Meta:
        db_table = "affiliate_clicks"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["affiliate", "created_at"]),
            models.Index(fields=["session_key", "product", "created_at"]),
        ]

    def __str__(self):
        return f"Click via {self.affiliate} on {self.product} at {self.created_at:%Y-%m-%d %H:%M}"
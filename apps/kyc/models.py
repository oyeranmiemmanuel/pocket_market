"""
Phase 1 - KYC collection & confirmation infrastructure
(see MARKETPLACE_BACKEND_IMPLEMENTATION.md).

This app is deliberately a COLLECTION layer, not a decision layer:
    Collect -> Validate -> Confirm/Review -> Store securely -> Track status
Nothing elsewhere in the codebase should read these models to make
pricing, ranking, dispatch, or eligibility decisions yet - that's an
explicit non-goal of this phase.

Each subject type gets its own dedicated model rather than one shared
polymorphic KYC blob, mirroring the rest of the project's "one model per
capability" pattern (SellerProfile/AffiliateProfile/RiderProfile). This
sits *beside* those existing profiles (which already carry business-
approval status) rather than duplicating their fields - it only adds
what's genuinely new: structured KYC submission metadata, its own review
lifecycle, and sensitive fields that need encryption/masking.
"""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.affiliates.models import AffiliateProfile
from apps.core.constants import DEFAULT_COUNTRY
from apps.core.enums import KYCStatus
from apps.core.fields import EncryptedCharField
from apps.core.models import BaseModel
from apps.riders.models import RiderProfile
from apps.sellers.models import SellerProfile


class IdentityDocumentType(models.TextChoices):
    NIN = "nin", "National ID Number (NIN)"
    PASSPORT = "passport", "International Passport"
    DRIVERS_LICENSE = "drivers_license", "Driver's Licence"
    VOTERS_CARD = "voters_card", "Voter's Card"
    CAC_CERTIFICATE = "cac_certificate", "CAC Certificate (Business)"


class BusinessType(models.TextChoices):
    INDIVIDUAL = "individual", "Individual / Sole Proprietor"
    REGISTERED_BUSINESS = "registered_business", "Registered Business"
    COMPANY = "company", "Limited Company"


class KYCBase(BaseModel):
    """
    Shared review lifecycle for every KYC subject type. Kept abstract (a
    separate table per concrete model, not one shared table) so each
    subclass gets its own correctly-typed reviewer FK, same as how
    SellerProfile/AffiliateProfile/RiderProfile each keep their own
    review fields rather than sharing one.
    """

    status = models.CharField(
        max_length=20,
        choices=KYCStatus.choices,
        default=KYCStatus.NOT_SUBMITTED,
    )

    submitted_at = models.DateTimeField(null=True, blank=True)

    reviewed_at = models.DateTimeField(null=True, blank=True)

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_reviews",
    )

    rejection_reason = models.TextField(blank=True)

    class Meta:
        abstract = True

    @property
    def is_confirmed(self):
        return self.status == KYCStatus.CONFIRMED


class BuyerKYC(KYCBase):
    """
    Phase 1 buyer KYC: basic personal/profile + address/contact info
    only. Intentionally NOT used for pricing, ranking, recommendations,
    or eligibility decisions - see module docstring. Stored as its own
    snapshot rather than read live off UserProfile, same reasoning
    SellerPayout snapshots bank details: what was confirmed shouldn't
    silently change if the user later edits their profile.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="kyc",
    )

    full_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address_line = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True, default=DEFAULT_COUNTRY)

    class Meta:
        db_table = "buyer_kyc"
        verbose_name = "Buyer KYC"
        verbose_name_plural = "Buyer KYC Records"

    def __str__(self):
        return f"{self.user} - Buyer KYC ({self.get_status_display()})"


def _seller_kyc_document_path(instance, filename):
    # Keyed by instance.pk (a UUID, already assigned at instantiation by
    # BaseModel) rather than a guessable slug - documents must never sit
    # at a predictable URL.
    return f"kyc/sellers/{instance.pk}/{filename}"


class SellerKYC(KYCBase):
    """
    Sits beside SellerProfile (which already owns store_name and the
    trading-approval status) - only adds what SellerProfile doesn't
    already have: structured business classification, a confirmed
    address, and identity/registration document metadata.
    """

    seller = models.OneToOneField(
        SellerProfile,
        on_delete=models.CASCADE,
        related_name="kyc",
    )

    business_type = models.CharField(max_length=30, choices=BusinessType.choices, blank=True)
    business_category = models.CharField(max_length=100, blank=True)

    business_address_line = models.CharField(max_length=255, blank=True)
    business_city = models.CharField(max_length=100, blank=True)
    business_state = models.CharField(max_length=100, blank=True)
    business_country = models.CharField(max_length=100, blank=True, default=DEFAULT_COUNTRY)

    contact_phone = models.CharField(max_length=20, blank=True)
    contact_email = models.EmailField(blank=True)

    id_document_type = models.CharField(max_length=30, choices=IdentityDocumentType.choices, blank=True)
    id_document_number = EncryptedCharField(max_length=64, blank=True)
    id_document_file = models.FileField(upload_to=_seller_kyc_document_path, blank=True, null=True)

    class Meta:
        db_table = "seller_kyc"
        verbose_name = "Seller KYC"
        verbose_name_plural = "Seller KYC Records"

    def __str__(self):
        return f"{self.seller} - Seller KYC ({self.get_status_display()})"


def _affiliate_kyc_document_path(instance, filename):
    return f"kyc/affiliates/{instance.pk}/{filename}"


class AffiliateKYC(KYCBase):
    affiliate = models.OneToOneField(
        AffiliateProfile,
        on_delete=models.CASCADE,
        related_name="kyc",
    )

    display_name = models.CharField(max_length=150, blank=True)
    business_type = models.CharField(max_length=30, choices=BusinessType.choices, blank=True)

    address_line = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True, default=DEFAULT_COUNTRY)

    contact_phone = models.CharField(max_length=20, blank=True)
    contact_email = models.EmailField(blank=True)

    id_document_type = models.CharField(max_length=30, choices=IdentityDocumentType.choices, blank=True)
    id_document_number = EncryptedCharField(max_length=64, blank=True)
    id_document_file = models.FileField(upload_to=_affiliate_kyc_document_path, blank=True, null=True)

    class Meta:
        db_table = "affiliate_kyc"
        verbose_name = "Affiliate KYC"
        verbose_name_plural = "Affiliate KYC Records"

    def __str__(self):
        return f"{self.affiliate} - Affiliate KYC ({self.get_status_display()})"


def _rider_kyc_document_path(instance, filename):
    return f"kyc/riders/{instance.pk}/documents/{filename}"


def _rider_kyc_license_path(instance, filename):
    return f"kyc/riders/{instance.pk}/license/{filename}"


class RiderKYC(KYCBase):
    """
    Holds the credentials RiderProfile deliberately doesn't (licence,
    vehicle, plate) so this phase can collect/confirm/store them without
    yet depending on them for dispatch, pricing, ranking, or payouts -
    per the spec. `plate_number` is left unencrypted (it's visible on
    the vehicle itself and will be needed operationally for pickup
    matching later); the licence number is encrypted.
    """

    rider = models.OneToOneField(
        RiderProfile,
        on_delete=models.CASCADE,
        related_name="kyc",
    )

    date_of_birth = models.DateField(null=True, blank=True)
    operating_location = models.CharField(max_length=150, blank=True)
    emergency_contact_name = models.CharField(max_length=150, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)

    id_document_type = models.CharField(max_length=30, choices=IdentityDocumentType.choices, blank=True)
    id_document_number = EncryptedCharField(max_length=64, blank=True)
    id_document_file = models.FileField(upload_to=_rider_kyc_document_path, blank=True, null=True)

    drivers_license_number = EncryptedCharField(max_length=64, blank=True)
    drivers_license_expiry = models.DateField(null=True, blank=True)
    drivers_license_file = models.FileField(upload_to=_rider_kyc_license_path, blank=True, null=True)

    vehicle_make = models.CharField(max_length=100, blank=True)
    vehicle_model = models.CharField(max_length=100, blank=True)
    vehicle_color = models.CharField(max_length=50, blank=True)
    plate_number = models.CharField(max_length=20, blank=True)

    class Meta:
        db_table = "rider_kyc"
        verbose_name = "Rider KYC"
        verbose_name_plural = "Rider KYC Records"

    def __str__(self):
        return f"{self.rider} - Rider KYC ({self.get_status_display()})"


class KYCAuditLog(BaseModel):
    """
    One shared audit trail for all four KYC subject types via a generic
    FK, instead of four near-identical log tables. Covers both status
    changes (submit/review/confirm/reject) and deliberate sensitive-field
    access (see apps.kyc.services.log_kyc_access) - per the spec's
    "audit logging for access and changes" requirement. Rows are only
    ever created by apps.kyc.services - never hand-edited.
    """

    class Action(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Moved Under Review"
        CONFIRMED = "confirmed", "Confirmed"
        REJECTED = "rejected", "Rejected"
        ACCESSED = "accessed", "Sensitive Field Accessed"

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    kyc_subject = GenericForeignKey("content_type", "object_id")

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="kyc_audit_actions",
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "kyc_audit_logs"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["content_type", "object_id"])]

    def __str__(self):
        return f"{self.get_action_display()} - {self.kyc_subject} - {self.created_at:%Y-%m-%d %H:%M}"
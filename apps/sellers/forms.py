from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory

from apps.catalog.models import Category, Product, ProductColorVariant, ProductImage, ProductSizeVariant
from apps.core.constants import (
    AFFILIATE_COMMISSION_RATE_MAX,
    AFFILIATE_COMMISSION_RATE_MIN,
    AFFILIATE_COMMISSION_RATE_SUGGESTED_DEFAULT,
)

from .models import SellerProfile


class SellerProductForm(forms.ModelForm):
    """
    A seller's own product form. Deliberately excludes `seller` and
    `commission_rate` - ownership is set server-side from the logged-in
    seller's profile (views.py), and the platform's own cut
    (`commission_rate`) is a platform/admin decision, not something a
    seller sets on themselves.

    `affiliate_commission_rate` IS seller-set here (Marketplace Frontend
    Roadmap, section 6) - it's what an affiliate earns for referring a
    sale of this specific product, which is the seller's own call to
    make, within the platform-wide 5-80% band.
    """

    class Meta:
        model = Product
        fields = [
            "category",
            "name",
            "description",
            "price",
            "image",
            "product_type",
            "digital_file",
            "stock",
            "affiliate_commission_rate",
            "is_active",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            # type="number" is the field a seller can type an exact
            # value into; the matching type="range" slider in
            # product_form.html is JS-synced to this same input by id
            # (id_affiliate_commission_rate) rather than being a second
            # Django field, so there's only ever one value posted.
            "affiliate_commission_rate": forms.NumberInput(attrs={
                "min": AFFILIATE_COMMISSION_RATE_MIN,
                "max": AFFILIATE_COMMISSION_RATE_MAX,
                "step": "1",
                "id": "id_affiliate_commission_rate",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.active.all()
        self.fields["category"].required = False

        # A seller is actively choosing this rate via the slider/gauge
        # control, not leaving it blank to fall through to the seller/
        # platform default further up the hierarchy - so, unlike the
        # model field, this is required on the form.
        commission_field = self.fields["affiliate_commission_rate"]
        commission_field.required = True
        commission_field.min_value = AFFILIATE_COMMISSION_RATE_MIN
        commission_field.max_value = AFFILIATE_COMMISSION_RATE_MAX
        if not self.instance.pk and self.initial.get("affiliate_commission_rate") is None:
            commission_field.initial = Decimal(str(AFFILIATE_COMMISSION_RATE_SUGGESTED_DEFAULT))

    def clean_affiliate_commission_rate(self):
        """
        Belt-and-braces on top of Product.affiliate_commission_rate's own
        MinValueValidator/MaxValueValidator: the UI (slider min/max + JS
        clamp) keeps a seller from *seeing* a way to submit an
        out-of-range value, but the roadmap is explicit that "backend
        validation remains mandatory" - so the range is re-checked here,
        server-side, regardless of what actually arrived in the POST body.
        """
        rate = self.cleaned_data.get("affiliate_commission_rate")
        if rate is None:
            raise ValidationError("Set an affiliate commission rate for this product.")
        if rate < AFFILIATE_COMMISSION_RATE_MIN or rate > AFFILIATE_COMMISSION_RATE_MAX:
            raise ValidationError(
                f"Affiliate commission must be between "
                f"{AFFILIATE_COMMISSION_RATE_MIN}% and "
                f"{AFFILIATE_COMMISSION_RATE_MAX}%."
            )
        return rate


# Gallery images, color variants, and size variants are edited alongside
# the product on the same page via inline formsets, rather than separate
# "manage images" / "manage variants" screens - matches how Django admin
# already presents them (see catalog/admin.py inlines) and keeps a
# seller's product-creation flow to one form submission.

ProductImageFormSet = inlineformset_factory(
    Product,
    ProductImage,
    fields=["image", "alt_text"],
    extra=3,
    max_num=ProductImage.MAX_IMAGES,
    validate_max=True,
    can_delete=True,
)

ProductColorVariantFormSet = inlineformset_factory(
    Product,
    ProductColorVariant,
    fields=["name", "hex_code"],
    extra=2,
    can_delete=True,
)

ProductSizeVariantFormSet = inlineformset_factory(
    Product,
    ProductSizeVariant,
    fields=["label"],
    extra=3,
    can_delete=True,
)


class SellerApplicationForm(forms.Form):
    store_name = forms.CharField(max_length=150)
    store_description = forms.CharField(widget=forms.Textarea, required=False)
    phone = forms.CharField(max_length=20)
    business_email = forms.EmailField()


class SellerBankDetailsForm(forms.ModelForm):
    """
    Phase 10 - only bank_code and account number are typed by the
    seller. bank_name and bank_account_name are always filled in
    server-side from Paystack's own bank list / account resolution (see
    views.bank_details_view) - never trusted from user input.
    """

    class Meta:
        model = SellerProfile
        fields = ["bank_name", "bank_account_number", "bank_account_name"]


class SellerStoreSettingsForm(forms.ModelForm):
    """Store profile fields shown to customers on the public store page (once it exists) -
    kept separate from SellerBankDetailsForm since bank info is sensitive and edited
    on its own page."""

    class Meta:
        model = SellerProfile
        fields = ["store_name", "store_description", "logo", "banner"]
        widgets = {
            "store_description": forms.Textarea(attrs={"rows": 4}),
        }

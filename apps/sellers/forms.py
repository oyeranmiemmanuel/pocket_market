from django import forms
from django.forms import inlineformset_factory

from apps.catalog.models import Category, Product, ProductColorVariant, ProductImage, ProductSizeVariant

from .models import SellerProfile


class SellerProductForm(forms.ModelForm):
    """
    A seller's own product form. Deliberately excludes `seller` and
    `commission_rate` - ownership is set server-side from the logged-in
    seller's profile (views.py), and per-product commission overrides are
    a platform/admin decision, not something a seller sets on themselves.
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
            "is_active",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.active.all()
        self.fields["category"].required = False


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

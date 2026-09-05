from django import forms
from decimal import Decimal
from apps.catalog.models import Category, Product

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
        fields = ["bank_code", "bank_account_number"]

class SellerPayoutRequestForm(forms.Form):
    amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))


class SellerStoreSettingsForm(forms.ModelForm):
    class Meta:
        model = SellerProfile
        fields = ["store_name", "store_description", "logo", "banner"]
        widgets = {
            "store_description": forms.Textarea(attrs={"rows": 4}),
        }
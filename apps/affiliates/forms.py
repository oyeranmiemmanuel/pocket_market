from django import forms
from decimal import Decimal  # add to top of file


from .models import AffiliateProfile


class AffiliateApplicationForm(forms.Form):
    """
    Spec section 3 - personal/business info, contact info, and
    promotional channels collected at application time. Mirrors
    apps.sellers.forms.SellerApplicationForm.
    """
    full_name = forms.CharField(max_length=150)
    phone = forms.CharField(max_length=20)
    contact_email = forms.EmailField(
        required=False,
        help_text="Optional - defaults to your account email if left blank.",
    )
    promotional_channels = forms.CharField(
        widget=forms.Textarea,
        help_text="Where do you plan to promote products? (blog, Instagram, YouTube, etc.)",
    )


class AffiliateBankDetailsForm(forms.ModelForm):
    class Meta:
        model = AffiliateProfile
        fields = ["bank_code", "bank_account_number"]


class AffiliatePayoutRequestForm(forms.Form):
    amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
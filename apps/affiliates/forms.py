from django import forms
from decimal import Decimal  # add to top of file


from .models import AffiliateProfile


class AffiliateBankDetailsForm(forms.ModelForm):
    class Meta:
        model = AffiliateProfile
        fields = ["bank_code", "bank_account_number"]


class AffiliatePayoutRequestForm(forms.Form):
    amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
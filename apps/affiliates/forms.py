from django import forms

from .models import AffiliateProfile


class AffiliateBankDetailsForm(forms.ModelForm):
    class Meta:
        model = AffiliateProfile
        fields = ["bank_name", "bank_account_number", "bank_account_name"]
from django import forms

from .models import RiderProfile, RiderVehicleType


class RiderApplicationForm(forms.Form):
    full_name = forms.CharField(max_length=150)
    phone = forms.CharField(max_length=20)
    contact_email = forms.EmailField(required=False)
    service_area = forms.CharField(max_length=150)
    vehicle_type = forms.ChoiceField(choices=RiderVehicleType.choices)


class RiderBankDetailsForm(forms.ModelForm):
    """
    Mirrors SellerBankDetailsForm - only the account number/bank code are
    typed by the rider. In a later phase, bank_name/bank_account_name
    should be resolved server-side via the payment provider's account
    resolution, never trusted as free text from the user, exactly like
    apps.sellers.views.bank_details_view already does.
    """

    class Meta:
        model = RiderProfile
        fields = ["bank_code", "bank_name", "bank_account_number", "bank_account_name"]
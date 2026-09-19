from django import forms

from apps.core.enums import DeliveryMethod


class CheckoutForm(forms.Form):
    """Contact info + shipping address + delivery method, in one step."""

    full_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    phone = forms.CharField(max_length=20)

    delivery_method = forms.ChoiceField(
        choices=DeliveryMethod.choices,
        widget=forms.RadioSelect,
        initial=DeliveryMethod.SHIPPING,
    )

    address_line1 = forms.CharField(max_length=255, label="Address")
    address_line2 = forms.CharField(max_length=255, required=False, label="Address (cont'd)")
    city = forms.CharField(max_length=100)
    state = forms.CharField(max_length=100)
    postal_code = forms.CharField(max_length=20, required=False)
    country = forms.CharField(max_length=100, initial="Nigeria")

    def shipping_data(self):
        return {
            "address_line1": self.cleaned_data["address_line1"],
            "address_line2": self.cleaned_data["address_line2"],
            "city": self.cleaned_data["city"],
            "state": self.cleaned_data["state"],
            "postal_code": self.cleaned_data["postal_code"],
            "country": self.cleaned_data["country"],
        }

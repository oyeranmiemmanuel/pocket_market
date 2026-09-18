from django import forms

from apps.core.enums import DeliveryMethod

from .models import SavedAddress


class CheckoutForm(forms.Form):
    """
    Contact info + delivery method + address, in one step.

    Address is either picked from the buyer's own SavedAddress book
    (Marketplace Frontend Roadmap section 19 - "Address selection") or
    typed fresh via the manual fields below - never both at once. See
    clean() for how the two interact.
    """

    full_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    phone = forms.CharField(max_length=20)

    delivery_method = forms.ChoiceField(
        choices=DeliveryMethod.choices,
        widget=forms.RadioSelect,
        initial=DeliveryMethod.SHIPPING,
    )

    saved_address = forms.ModelChoiceField(
        queryset=SavedAddress.objects.none(),
        required=False,
        empty_label="Use a new address",
        label="Saved address",
    )
    save_address = forms.BooleanField(
        required=False, initial=False, label="Save this address for next time",
    )

    # required=False at the field level - clean() below enforces these
    # only when saved_address wasn't picked, since a saved address
    # supplies its own values instead.
    address_line1 = forms.CharField(max_length=255, label="Address", required=False)
    address_line2 = forms.CharField(max_length=255, required=False, label="Address (cont'd)")
    city = forms.CharField(max_length=100, required=False)
    state = forms.CharField(max_length=100, required=False)
    postal_code = forms.CharField(max_length=20, required=False)
    country = forms.CharField(max_length=100, required=False, initial="Nigeria")

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None and getattr(user, "is_authenticated", False):
            self.fields["saved_address"].queryset = SavedAddress.objects.filter(user=user)
        else:
            # Guest/unauthenticated - nothing to save or pick from, so
            # don't even show the controls (checkout itself is
            # login_required today, but this form shouldn't assume that
            # stays true forever).
            del self.fields["saved_address"]
            del self.fields["save_address"]

    def clean(self):
        cleaned = super().clean()
        saved = cleaned.get("saved_address")

        if saved:
            # A picked saved address always wins over the manual fields -
            # those exist only for "Use a new address".
            cleaned["address_line1"] = saved.address_line1
            cleaned["address_line2"] = saved.address_line2
            cleaned["city"] = saved.city
            cleaned["state"] = saved.state
            cleaned["postal_code"] = saved.postal_code
            cleaned["country"] = saved.country
            cleaned["save_address"] = False  # already saved - nothing new to save
        else:
            for field_name in ("address_line1", "city", "state", "country"):
                if not cleaned.get(field_name):
                    self.add_error(field_name, "This field is required.")

        return cleaned

    def shipping_data(self):
        return {
            "address_line1": self.cleaned_data["address_line1"],
            "address_line2": self.cleaned_data.get("address_line2", ""),
            "city": self.cleaned_data["city"],
            "state": self.cleaned_data["state"],
            "postal_code": self.cleaned_data.get("postal_code", ""),
            "country": self.cleaned_data["country"],
        }

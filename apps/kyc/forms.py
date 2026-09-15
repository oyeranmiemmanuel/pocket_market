from django import forms

from .models import AffiliateKYC, BuyerKYC, RiderKYC, SellerKYC


class BuyerKYCForm(forms.ModelForm):
    class Meta:
        model = BuyerKYC
        fields = ["full_name", "phone", "address_line", "city", "state", "country"]


class SellerKYCForm(forms.ModelForm):
    class Meta:
        model = SellerKYC
        fields = [
            "business_type", "business_category",
            "business_address_line", "business_city", "business_state", "business_country",
            "contact_phone", "contact_email",
            "id_document_type", "id_document_number", "id_document_file",
        ]


class AffiliateKYCForm(forms.ModelForm):
    class Meta:
        model = AffiliateKYC
        fields = [
            "display_name", "business_type",
            "address_line", "city", "state", "country",
            "contact_phone", "contact_email",
            "id_document_type", "id_document_number", "id_document_file",
        ]


class RiderKYCForm(forms.ModelForm):
    class Meta:
        model = RiderKYC
        fields = [
            "date_of_birth", "operating_location",
            "emergency_contact_name", "emergency_contact_phone",
            "id_document_type", "id_document_number", "id_document_file",
            "drivers_license_number", "drivers_license_expiry", "drivers_license_file",
            "vehicle_make", "vehicle_model", "vehicle_color", "plate_number",
        ]
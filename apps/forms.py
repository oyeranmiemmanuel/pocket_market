from django import forms
from .models import ContactMessage
from apps.catalog.models import Product


class PasswordVerificationForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput, label="Verify Password")


class MessageForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'subject', 'message']


class ProductForm(forms.ModelForm):

    class Meta:
        model = Product
        fields = [
            'name',
            'description',
            'price',
            'image',
            'product_type',
            'digital_file',
            'stock',
            'is_active',
        ]

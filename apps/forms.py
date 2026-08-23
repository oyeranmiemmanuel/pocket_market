from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import ContactMessage
from apps.catalog.models import Product

User = get_user_model()


class AdminSignupForm(UserCreationForm):
    """
    Staff/admin signup for the custom admin panel (custom_signup view).

    Plain UserCreationForm has no email field at all - the template was
    already rendering {{ form.email }}, but since the form never defined
    it, whatever the user typed was silently dropped, user.email stayed
    blank, and the verification email (sent via send_verification_email)
    had nowhere real to go. This subclass actually defines the field so
    it's validated and saved.
    """

    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


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

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError

from .models import UserProfile

User = get_user_model()


class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email Address'
        })
    )

    # first_name / last_name / phone live on UserProfile, not on User, so
    # they're plain form fields here rather than in Meta.fields below -
    # register_view() saves them onto the UserProfile it creates.
    first_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'First Name'}),
    )
    last_name = forms.CharField(
        max_length=100,
        required=True,
        label="Surname",
        widget=forms.TextInput(attrs={'placeholder': 'Surname'}),
    )
    phone = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'Phone Number'}),
    )

    class Meta:
        model = User
        fields = (
            'username',
            'email',
            'password1',
            'password2',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        classes = (
            "w-full bg-transparent px-4 py-3 "
            "text-white placeholder-gray-400 "
            "focus:outline-none"
        )

        for field in self.fields.values():
            field.widget.attrs.update({
                "class": classes
            })

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class LoginForm(forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)


class ProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ("first_name", "last_name", "phone", "country", "avatar", "bio")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        text_classes = (
            "w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm "
            "focus:outline-none focus:border-indigo-400"
        )

        for name, field in self.fields.items():
            if name == "avatar":
                field.widget.attrs.update({"class": "text-sm"})
            elif name == "bio":
                field.widget.attrs.update({"class": text_classes, "rows": 4})
            else:
                field.widget.attrs.update({"class": text_classes})
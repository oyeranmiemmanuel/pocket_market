from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

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

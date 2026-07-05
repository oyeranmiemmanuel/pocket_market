from django import forms
from .models import ContactMessage, UserProfile, Product
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm



class SignupForm(UserCreationForm):
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

    def save(self, commit=True):
        user = super().save(commit=False)

        user.email = self.cleaned_data['email']

        if commit:
            user.save()

        return user

class LoginForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)

class PasswordVerificationForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput, label="Verify Password")



class MessageForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'subject', 'message']



class RegisterForm(UserCreationForm):

    first_name = forms.CharField(max_length=100)

    other_names = forms.CharField(max_length=200)

    date_of_birth = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'})
    )

    phone = forms.CharField(max_length=20)

    email = forms.EmailField()

    class Meta:
        model = User

        fields = [
            'first_name',
            'other_names',
            'email',
            'phone',
            'date_of_birth',
            'password1',
            'password2'
        ]


class CreateNewList(forms.Form):
    name = forms.CharField(label="Name", max_length=200)
    check = forms.BooleanField(required=False)



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
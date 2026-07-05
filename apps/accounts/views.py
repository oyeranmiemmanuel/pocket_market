from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render

from .forms import LoginForm, RegisterForm
from .models import UserProfile


def register_view(request):
    """Customer signup. Replaces the old monolith's signup() view."""

    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = RegisterForm(request.POST)

        if form.is_valid():
            user = form.save()

            # Profile row starts empty - user fills in phone/country/etc
            # later from their account page, rather than at signup time.
            UserProfile.objects.create(user=user)

            login(request, user)

            messages.success(request, "Account created successfully!")

            return redirect('home')
    else:
        form = RegisterForm()

    return render(request, 'accounts/signup.html', {'form': form})


def login_view(request):
    """Customer login. Replaces the old monolith's user_login() view."""

    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = LoginForm(request.POST)

        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'],
            )

            if user is not None:
                login(request, user)
                messages.success(request, "Login successful!")
                return redirect('home')

            messages.error(request, "Invalid username or password.")
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    """Replaces the old monolith's user_logout() view."""
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('accounts:login')

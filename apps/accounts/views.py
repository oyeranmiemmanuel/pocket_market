from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.core.mail import send_mail
from django.conf import settings
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import url_has_allowed_host_and_scheme, urlsafe_base64_decode, urlsafe_base64_encode
from django.core.mail import EmailMultiAlternatives

from apps.cart.services import merge_guest_cart_into_user

from .forms import LoginForm, RegisterForm
from .models import UserProfile
from .tokens import email_verification_token

User = get_user_model()


def _safe_next_url(request, default='home'):
    """
    Reads ?next= (GET or POST) and returns it only if it's a safe local
    redirect target - never trust this value blindly, it comes straight
    from the URL.
    """
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return default



def _send_verification_email(request, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)

    verify_url = request.build_absolute_uri(
        f"/accounts/verify-email/{uid}/{token}/"
    )

    subject = "Verify your TopTech account"

    context = {
        "user": user,
        "verify_url": verify_url,
    }

    text_content = render_to_string(
        "accounts/verification_email.txt",
        context,
    )

    html_content = render_to_string(
        "accounts/verification_email.html",
        context,
    )

    email = EmailMultiAlternatives(
        subject,
        text_content,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
    )

    email.attach_alternative(html_content, "text/html")
    email.send(fail_silently=False)

def register_view(request):
    """Customer signup. Replaces the old monolith's signup() view.

    Account starts inactive until the email verification link is clicked
    - see 09_AUTHENTICATION.md.
    """

    if request.user.is_authenticated:
        return redirect('home')

    next_url = _safe_next_url(request, default='')

    if request.method == 'POST':
        form = RegisterForm(request.POST)

        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.save()

            # Profile row starts empty - user fills in phone/country/etc
            # later from their account page, rather than at signup time.
            UserProfile.objects.create(user=user)

            _send_verification_email(request, user)

            messages.success(
                request,
                "Account created! Check your email for a verification link before logging in."
            )

            login_url = 'accounts:login'
            if next_url:
                login_url += f'?next={next_url}'
            return redirect(login_url)
    else:
        form = RegisterForm()

    return render(request, 'accounts/signup.html', {'form': form, 'next': next_url})


def verify_email(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and email_verification_token.check_token(user, token):
        user.is_active = True
        user.save(update_fields=['is_active'])
        messages.success(request, "Email verified! You can now log in.")
    else:
        messages.error(request, "Verification link is invalid or has expired.")

    return redirect('accounts:login')


def login_view(request):
    """Customer login. Replaces the old monolith's user_login() view."""

    if request.user.is_authenticated:
        return redirect('home')

    next_url = _safe_next_url(request, default='home')

    if request.method == 'POST':
        form = LoginForm(request.POST)

        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']

            user = authenticate(request, username=username, password=password)

            if user is not None:
                # Must run before login() - it cycles the session key,
                # after which the guest cart's session_key won't match.
                merge_guest_cart_into_user(request, user)

                login(request, user)
                messages.success(request, "Login successful!")
                return redirect(next_url)

            # authenticate() also returns None for correct credentials on
            # an inactive (unverified) account - check for that case
            # separately so the message is actually helpful.
            existing = User.objects.filter(username=username).first()
            if existing is not None and not existing.is_active and existing.check_password(password):
                messages.error(request, "Please verify your email before logging in.")
            else:
                messages.error(request, "Invalid username or password.")
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form, 'next': next_url if next_url != 'home' else ''})


def logout_view(request):
    """Replaces the old monolith's user_logout() view."""
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('accounts:login')

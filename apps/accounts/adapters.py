from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.cart.services import merge_guest_cart_into_user

from .models import UserProfile

User = get_user_model()


class AccountAdapter(DefaultAccountAdapter):
    """
    Adapter for the plain username/password flow. register_view() and
    login_view() already do the real work - this only exists so allauth's
    own internal redirects point at the products page rather than
    Django's default '/accounts/profile/'. Deliberately independent of
    the LOGIN_REDIRECT_URL setting, which is for the separate admin login.
    """

    def get_login_redirect_url(self, request):
        return reverse("catalog:product_list")


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Without this, a user who originally signed up with username/password
    and later clicks "Continue with Google" using the same email gets
    blocked by allauth with "A user is already registered with this
    email address" instead of just being logged in. pre_social_login()
    intercepts that case and connects the Google account to the existing
    local user instead of erroring out.
    """

    def get_connect_redirect_url(self, request, socialaccount):
       return reverse("catalog:product_list")

    def pre_social_login(self, request, sociallogin):
        # Already linked to a SocialAccount from a previous login -
        # nothing to do, let allauth proceed normally.
        if sociallogin.is_existing:
            return

        email = (sociallogin.account.extra_data.get('email')
                 or sociallogin.user.email)
        if not email:
            return

        existing_user = (
            User.objects.filter(email__iexact=email).order_by('pk').first()
        )
        if existing_user is None:
            return

        # Google has already verified this address, so an account that
        # was sitting inactive/unverified from the username/password flow
        # can be safely activated here.
        if not existing_user.is_active:
            existing_user.is_active = True
            existing_user.save(update_fields=['is_active'])

        sociallogin.connect(request, existing_user)

        # Same ordering rule as login_view(): this has to happen before
        # allauth calls django's login() and cycles the session key, or
        # the guest cart's session_key stops matching.
        merge_guest_cart_into_user(request, existing_user)

    def is_auto_signup_allowed(self, request, sociallogin):
        # Skip allauth's intermediate "confirm your email/username" form -
        # go straight from the Google consent screen to a logged-in user.
        return True

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)

        # Brand-new Google signup: no email-verification gate needed.
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=['is_active'])

        # allauth's Google provider populates user.first_name/last_name
        # from the Google profile, but the rest of this app reads names
        # off UserProfile (see ProfileForm) - copy them across so a
        # Google signup looks the same as an email signup everywhere else.
        profile, _ = UserProfile.objects.get_or_create(user=user)
        if not profile.first_name and user.first_name:
            profile.first_name = user.first_name
        if not profile.last_name and user.last_name:
            profile.last_name = user.last_name
        profile.save()

        # save_user() runs before allauth's login() call for a brand-new
        # signup, so this is the right moment - same ordering rule as
        # login_view() and pre_social_login() above.
        merge_guest_cart_into_user(request, user)

        return user
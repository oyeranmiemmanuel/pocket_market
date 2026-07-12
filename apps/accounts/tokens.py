from django.contrib.auth.tokens import PasswordResetTokenGenerator


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """
    Same idea as Django's built-in password reset token, but the hash
    includes is_active so a token is automatically invalidated the moment
    the account gets verified (can't be reused/replayed afterward).
    """

    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{timestamp}{user.is_active}"


email_verification_token = EmailVerificationTokenGenerator()

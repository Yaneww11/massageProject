from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model


class ClosedSignupAccountAdapter(DefaultAccountAdapter):
    """Local (email/password) allauth signup stays closed -- registration
    happens through the booking auth modal, which enforces OTP verification
    and the phone-number requirement."""

    def is_open_for_signup(self, request):
        return False


class GoogleSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Auto-link a first-time Google login to an existing account with the
    same email. Existing users have no allauth EmailAddress records, so the
    built-in SOCIALACCOUNT_EMAIL_AUTHENTICATION matching would never find
    them; we match on CustomUser.email directly. Only provider-verified
    emails are trusted (Google always verifies)."""

    def is_open_for_signup(self, request, sociallogin):
        # The default delegates to the account adapter, which is closed;
        # social signup (the Google complete-profile step) must stay open.
        return True

    def pre_social_login(self, request, sociallogin):
        if sociallogin.is_existing:
            return
        verified_emails = [
            address.email.lower()
            for address in sociallogin.email_addresses
            if address.verified
        ]
        if not verified_emails:
            return
        User = get_user_model()
        user = User.objects.filter(email__iexact=verified_emails[0]).first()
        if user is not None:
            sociallogin.connect(request, user)

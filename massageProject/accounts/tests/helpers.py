from django.contrib.auth import get_user_model

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialLogin

User = get_user_model()


def make_sociallogin(email, first_name='Иван', last_name='Петров', uid='google-uid-1'):
    """Build the SocialLogin object the Google adapter would produce after
    a successful OAuth callback, without talking to Google."""
    user = User(email=email, first_name=first_name, last_name=last_name)
    account = SocialAccount(provider='google', uid=uid, extra_data={'email': email})
    sociallogin = SocialLogin(user=user, account=account)
    sociallogin.email_addresses = [
        EmailAddress(email=email, verified=True, primary=True),
    ]
    return sociallogin


def google_profile(email, first_name='Иван', last_name='Петров', uid='google-uid-1'):
    """The decoded id-token payload Google would return for this user."""
    return {
        'sub': uid,
        'email': email,
        'email_verified': True,
        'given_name': first_name,
        'family_name': last_name,
    }

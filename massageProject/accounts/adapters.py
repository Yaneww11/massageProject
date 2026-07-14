from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class ClosedSignupAccountAdapter(DefaultAccountAdapter):
    pass


class GoogleSocialAccountAdapter(DefaultSocialAccountAdapter):
    pass

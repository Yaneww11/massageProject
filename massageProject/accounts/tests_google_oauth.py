from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialLogin

User = get_user_model()

TEST_PROVIDERS = {
    'google': {
        'APP': {'client_id': 'test-client-id', 'secret': 'test-secret'},
        'SCOPE': ['profile', 'email'],
    },
}


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


class GoogleCallbackTestMixin:
    """Drives a real /accounts/google/login/ -> callback round-trip with the
    Google token exchange mocked out."""

    def run_google_callback(self, sociallogin, next_url=''):
        data = {'next': next_url} if next_url else {}
        start = self.client.post(reverse('google_login'), data)
        self.assertEqual(start.status_code, 302)
        state = parse_qs(urlparse(start['Location']).query)['state'][0]
        with patch(
            'allauth.socialaccount.providers.google.views.GoogleOAuth2Adapter.complete_login',
            return_value=sociallogin,
        ), patch(
            'allauth.socialaccount.providers.oauth2.client.OAuth2Client.get_access_token',
            return_value={'access_token': 'dummy-token'},
        ):
            return self.client.get(
                reverse('google_callback'), {'code': 'dummy-code', 'state': state}
            )


@override_settings(SOCIALACCOUNT_PROVIDERS=TEST_PROVIDERS)
class GoogleWiringTests(TestCase):
    def test_google_login_redirects_to_google(self):
        response = self.client.post(reverse('google_login'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            response['Location'].startswith('https://accounts.google.com/o/oauth2/'),
            response['Location'],
        )

    def test_existing_login_route_still_serves_custom_view(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/auth_entry.html')

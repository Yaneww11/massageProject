from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialLogin

from massageProject.accounts.forms import SocialCompleteProfileForm

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


def google_profile(email, first_name='Иван', last_name='Петров', uid='google-uid-1'):
    """The decoded id-token payload Google would return for this user."""
    return {
        'sub': uid,
        'email': email,
        'email_verified': True,
        'given_name': first_name,
        'family_name': last_name,
    }


class GoogleCallbackTestMixin:
    """Drives a real /accounts/google/login/ -> callback round-trip with the
    Google token exchange mocked out. The sociallogin is built through the
    real provider machinery so it carries the provider/app wiring allauth
    relies on."""

    def run_google_callback(self, profile, next_url=''):
        data = {'next': next_url} if next_url else {}
        start = self.client.post(reverse('google_login'), data)
        self.assertEqual(start.status_code, 302)
        state = parse_qs(urlparse(start['Location']).query)['state'][0]

        def fake_complete_login(request, app, token, **kwargs):
            return app.get_provider(request).sociallogin_from_response(request, profile)

        with patch(
            'allauth.socialaccount.providers.google.views.GoogleOAuth2Adapter.complete_login',
            side_effect=fake_complete_login,
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


@override_settings(SOCIALACCOUNT_PROVIDERS=TEST_PROVIDERS)
class AdapterTests(GoogleCallbackTestMixin, TestCase):
    def test_local_allauth_signup_is_closed(self):
        response = self.client.get(reverse('account_signup'))
        self.assertTemplateUsed(response, 'account/signup_closed.html')

    def test_google_login_with_known_email_links_and_logs_in(self):
        user = User.objects.create_user(
            email='known@example.com', phone_number='0899123456', password='Str0ng-pass1',
        )
        response = self.run_google_callback(google_profile('known@example.com'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)
        self.assertTrue(
            SocialAccount.objects.filter(user=user, provider='google').exists()
        )

    def test_returning_google_user_logs_straight_in(self):
        user = User.objects.create_user(
            email='returning@example.com', phone_number='0899123457', password='Str0ng-pass1',
        )
        SocialAccount.objects.create(user=user, provider='google', uid='google-uid-1')
        response = self.run_google_callback(google_profile('returning@example.com'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

    def test_unknown_email_is_sent_to_complete_profile(self):
        response = self.run_google_callback(google_profile('newcomer@gmail.com'))
        self.assertRedirects(
            response, reverse('socialaccount_signup'), fetch_redirect_response=False
        )
        self.assertEqual(User.objects.count(), 0)


@override_settings(SOCIALACCOUNT_PROVIDERS=TEST_PROVIDERS)
class SocialCompleteProfileFormTests(TestCase):
    def form(self, data=None, email='newcomer@gmail.com'):
        return SocialCompleteProfileForm(data=data, sociallogin=make_sociallogin(email))

    def test_names_are_prefilled_from_google(self):
        form = self.form()
        self.assertEqual(form.initial.get('first_name'), 'Иван')
        self.assertEqual(form.initial.get('last_name'), 'Петров')

    def test_phone_is_required(self):
        form = self.form(data={
            'email': 'newcomer@gmail.com', 'first_name': 'Иван',
            'last_name': 'Петров', 'phone_number': '',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('phone_number', form.errors)

    def test_invalid_phone_format_is_rejected(self):
        form = self.form(data={
            'email': 'newcomer@gmail.com', 'first_name': 'Иван',
            'last_name': 'Петров', 'phone_number': '123456',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('phone_number', form.errors)

    def test_phone_is_normalized(self):
        form = self.form(data={
            'email': 'newcomer@gmail.com', 'first_name': 'Иван',
            'last_name': 'Петров', 'phone_number': '+359899123456',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['phone_number'], '0899123456')

    def test_date_of_birth_is_optional(self):
        form = self.form(data={
            'email': 'newcomer@gmail.com', 'first_name': 'Иван',
            'last_name': 'Петров', 'phone_number': '0899123456',
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_phone_of_registered_user_is_rejected(self):
        User.objects.create_user(
            email='taken@example.com', phone_number='0899123456', password='Str0ng-pass1',
        )
        form = self.form(data={
            'email': 'newcomer@gmail.com', 'first_name': 'Иван',
            'last_name': 'Петров', 'phone_number': '0899123456',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('phone_number', form.errors)

    def test_phone_of_passwordless_user_is_claimable(self):
        staff_created = User.objects.create_user(
            email='placeholder@example.com', phone_number='0899123456', password=None,
        )
        form = self.form(data={
            'email': 'newcomer@gmail.com', 'first_name': 'Иван',
            'last_name': 'Петров', 'phone_number': '0899123456',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form._claimed_user, staff_created)

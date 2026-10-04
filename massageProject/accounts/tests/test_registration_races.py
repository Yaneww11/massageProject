from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from massageProject.accounts.forms import SocialCompleteProfileForm
from massageProject.accounts.models import CustomUser
from massageProject.accounts.tests.helpers import make_sociallogin

TURNSTILE_PATCH = 'massageProject.accounts.booking_auth_views.verify_turnstile_token'


class RegistrationEmailRaceTest(TestCase):
    """1.5 — a concurrent email collision at save-time must return a graceful
    error instead of an unhandled IntegrityError/500."""

    def setUp(self):
        cache.clear()
        self.client = Client()

    def _session_with_verified_email(self, email):
        from massageProject.accounts.booking_auth_views import SIGNUP_EMAIL_SESSION_KEY
        session = self.client.session
        session[SIGNUP_EMAIL_SESSION_KEY] = email
        session[SIGNUP_EMAIL_SESSION_KEY + '_expires'] = (
            timezone.now() + timezone.timedelta(minutes=15)
        ).isoformat()
        session.save()

    @patch(TURNSTILE_PATCH, return_value=True)
    def test_email_taken_between_verification_and_save_returns_409_not_500(self, mock_turnstile):
        CustomUser.objects.create_user(
            phone_number='0888920001', email='raced@example.com', password='Whatever!123',
        )
        self._session_with_verified_email('raced@example.com')

        response = self.client.post(reverse('auth_register'), {
            'first_name': 'Petar', 'last_name': 'Georgiev',
            'phone_number': '0888920002', 'password': 'ComplexPass!123',
            'turnstile_token': 'ok',
        })

        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.json()['success'])
        self.assertEqual(CustomUser.objects.filter(phone_number='0888920002').count(), 0)


class SocialClaimConcurrencyGuardTest(TestCase):
    """1.6 — a phone number claimed concurrently (password set in between
    validation and save) must fail loudly, not silently overwrite."""

    def test_save_rechecks_password_after_locking_and_raises_instead_of_overwriting(self):
        User = get_user_model()
        staff_created = User.objects.create_user(
            email='placeholder@example.com', phone_number='0899555001', password=None,
        )
        sociallogin = make_sociallogin('newcomer@example.com')
        form = SocialCompleteProfileForm(data={
            'email': 'newcomer@example.com', 'first_name': 'Ivan',
            'last_name': 'Petrov', 'phone_number': '0899555001',
        }, sociallogin=sociallogin)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form._claimed_user, staff_created)

        # Simulate a concurrent request setting a password on this same
        # passwordless user after our clean() ran but before our save().
        staff_created.set_password('someone-else-claimed-this')
        staff_created.save()

        request = RequestFactory().post('/accounts/social/signup/')
        with self.assertRaises(ValidationError):
            form.save(request)

        staff_created.refresh_from_db()
        self.assertEqual(staff_created.email, 'placeholder@example.com')
        self.assertEqual(staff_created.first_name, '')

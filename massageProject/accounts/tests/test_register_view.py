from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

User = get_user_model()

TURNSTILE_PATCH = 'massageProject.accounts.booking_auth_views.verify_turnstile_token'


class RegisterViewTest(TestCase):
    def setUp(self):
        cache.clear()

    def _session_with_verified_email(self, email):
        from massageProject.accounts.booking_auth_views import SIGNUP_EMAIL_SESSION_KEY

        session = self.client.session
        session[SIGNUP_EMAIL_SESSION_KEY] = email
        session[SIGNUP_EMAIL_SESSION_KEY + '_expires'] = (
            timezone.now() + timezone.timedelta(minutes=15)
        ).isoformat()
        session.save()

    @patch(TURNSTILE_PATCH, return_value=True)
    def test_valid_submission_creates_active_logged_in_user(self, mock_turnstile):
        self._session_with_verified_email('newbooker@example.com')
        response = self.client.post(reverse('auth_register'), {
            'first_name': 'Petar', 'last_name': 'Georgiev',
            'phone_number': '0888910001', 'password': 'ComplexPass!123',
            'turnstile_token': 'ok',
        })
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['status'], 'registered')

        user = User.objects.get(email='newbooker@example.com')
        self.assertTrue(user.is_active)

        resp = self.client.get(reverse('profile_page'))
        self.assertTrue(resp.wsgi_request.user.is_authenticated)

    def test_missing_verified_session_is_rejected(self):
        response = self.client.post(reverse('auth_register'), {
            'first_name': 'Petar', 'last_name': 'Georgiev',
            'phone_number': '0888910002', 'password': 'ComplexPass!123',
            'turnstile_token': 'ok',
        })
        self.assertEqual(response.status_code, 403)
        self.assertEqual(User.objects.filter(phone_number='0888910002').count(), 0)

    def test_honeypot_field_filled_returns_fake_success_without_creating_user(self):
        self._session_with_verified_email('bot@example.com')
        response = self.client.post(reverse('auth_register'), {
            'first_name': 'Bot', 'last_name': 'Bot',
            'phone_number': '0888910003', 'password': 'ComplexPass!123',
            'middle_name': 'i-am-a-bot',
            'turnstile_token': 'ok',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertEqual(User.objects.filter(email='bot@example.com').count(), 0)

    @patch(TURNSTILE_PATCH, return_value=False)
    def test_failed_turnstile_check_is_rejected(self, mock_turnstile):
        self._session_with_verified_email('suspicious@example.com')
        response = self.client.post(reverse('auth_register'), {
            'first_name': 'Test', 'last_name': 'User',
            'phone_number': '0888910004', 'password': 'ComplexPass!123',
            'turnstile_token': 'bad',
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(User.objects.filter(email='suspicious@example.com').count(), 0)

    @patch(TURNSTILE_PATCH, return_value=True)
    def test_invalid_form_data_returns_field_errors(self, mock_turnstile):
        self._session_with_verified_email('bad@example.com')
        response = self.client.post(reverse('auth_register'), {
            'first_name': '', 'last_name': '',
            'phone_number': '0888910005', 'password': 'ComplexPass!123',
            'turnstile_token': 'ok',
        })
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('first_name', data['errors'])

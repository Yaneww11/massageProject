import re
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

User = get_user_model()

TURNSTILE_PATCH = 'massageProject.accounts.booking_auth_views.verify_turnstile_token'


def _extract_code(email_body):
    match = re.search(r'\b(\d{6})\b', email_body)
    assert match, 'no 6-digit code found in email body'
    return match.group(1)


class NewUserBookingAuthFlowTest(TestCase):
    def setUp(self):
        cache.clear()

    @patch(TURNSTILE_PATCH, return_value=True)
    def test_full_signup_round_trip(self, mock_turnstile):
        email = 'brandnew@example.com'

        check_resp = self.client.post(reverse('auth_check_email'), {'email': email})
        self.assertFalse(check_resp.json()['exists'])

        send_resp = self.client.post(reverse('auth_send_code'), {
            'email': email, 'turnstile_token': 'ok',
        })
        self.assertTrue(send_resp.json()['success'])
        self.assertEqual(len(mail.outbox), 1)

        code = _extract_code(mail.outbox[0].body)

        verify_resp = self.client.post(reverse('auth_verify_code'), {'email': email, 'code': code})
        verify_data = verify_resp.json()
        self.assertTrue(verify_data['success'])
        self.assertEqual(verify_data['status'], 'verified')

        register_resp = self.client.post(reverse('auth_register'), {
            'first_name': 'Nova', 'last_name': 'User',
            'phone_number': '0888950001', 'password': 'ComplexPass!123',
            'turnstile_token': 'ok',
        })
        register_data = register_resp.json()
        self.assertTrue(register_data['success'])
        self.assertEqual(register_data['status'], 'registered')

        user = User.objects.get(email=email)
        self.assertTrue(user.is_active)

        profile_resp = self.client.get(reverse('profile_page'))
        self.assertTrue(profile_resp.wsgi_request.user.is_authenticated)
        self.assertEqual(profile_resp.wsgi_request.user.pk, user.pk)


class ExistingUserBookingAuthFlowTest(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email='returning@example.com', phone_number='0888950002', password='ComplexPass!123',
        )

    def test_existing_user_logs_in_with_password(self):
        check_resp = self.client.post(reverse('auth_check_email'), {'email': 'returning@example.com'})
        self.assertTrue(check_resp.json()['exists'])

        login_resp = self.client.post(reverse('auth_login_password'), {
            'email': 'returning@example.com', 'password': 'ComplexPass!123',
        })
        data = login_resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['status'], 'logged_in')

        profile_resp = self.client.get(reverse('profile_page'))
        self.assertTrue(profile_resp.wsgi_request.user.is_authenticated)
        self.assertEqual(profile_resp.wsgi_request.user.pk, self.user.pk)

    @patch(TURNSTILE_PATCH, return_value=True)
    def test_existing_user_logs_in_with_emailed_code(self, mock_turnstile):
        send_resp = self.client.post(reverse('auth_send_code'), {
            'email': 'returning@example.com', 'turnstile_token': 'ok',
        })
        self.assertTrue(send_resp.json()['success'])
        code = _extract_code(mail.outbox[0].body)

        verify_resp = self.client.post(reverse('auth_verify_code'), {
            'email': 'returning@example.com', 'code': code,
        })
        data = verify_resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['status'], 'logged_in')

        profile_resp = self.client.get(reverse('profile_page'))
        self.assertTrue(profile_resp.wsgi_request.user.is_authenticated)
        self.assertEqual(profile_resp.wsgi_request.user.pk, self.user.pk)

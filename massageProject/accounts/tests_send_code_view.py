from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from massageProject.accounts.models import EmailOTP

User = get_user_model()

TURNSTILE_PATCH = 'massageProject.accounts.booking_auth_views.verify_turnstile_token'


class SendCodeViewTest(TestCase):
    def setUp(self):
        cache.clear()

    @patch(TURNSTILE_PATCH, return_value=True)
    def test_sends_an_email_with_a_code_for_a_new_signup(self, mock_turnstile):
        response = self.client.post(reverse('auth_send_code'), {
            'email': 'newsignup@example.com', 'turnstile_token': 'good',
        })
        self.assertTrue(response.json()['success'])
        self.assertEqual(len(mail.outbox), 1)
        otp = EmailOTP.objects.live_for_email('newsignup@example.com').first()
        self.assertIsNotNone(otp)
        self.assertEqual(otp.purpose, EmailOTP.PURPOSE_SIGNUP)

    @patch(TURNSTILE_PATCH, return_value=True)
    def test_purpose_is_login_for_an_existing_users_email(self, mock_turnstile):
        User.objects.create_user(email='existing@example.com', phone_number='0888930001', password='pass1234')
        self.client.post(reverse('auth_send_code'), {
            'email': 'existing@example.com', 'turnstile_token': 'good',
        })
        otp = EmailOTP.objects.live_for_email('existing@example.com').first()
        self.assertEqual(otp.purpose, EmailOTP.PURPOSE_LOGIN)

    @patch(TURNSTILE_PATCH, return_value=False)
    def test_failed_turnstile_check_is_rejected_and_sends_no_email(self, mock_turnstile):
        response = self.client.post(reverse('auth_send_code'), {
            'email': 'suspicious@example.com', 'turnstile_token': 'bad',
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(mail.outbox), 0)

    @patch(TURNSTILE_PATCH, return_value=True)
    def test_sixth_request_from_the_same_ip_within_a_minute_is_rate_limited(self, mock_turnstile):
        for i in range(5):
            resp = self.client.post(reverse('auth_send_code'), {
                'email': 'ratelimit{}@example.com'.format(i), 'turnstile_token': 'good',
            })
            self.assertEqual(resp.status_code, 200)
        resp = self.client.post(reverse('auth_send_code'), {
            'email': 'ratelimitX@example.com', 'turnstile_token': 'good',
        })
        self.assertEqual(resp.status_code, 429)

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from massageProject.accounts.models import EmailOTP

User = get_user_model()


class VerifyCodeViewTest(TestCase):
    def setUp(self):
        cache.clear()

    def test_correct_code_for_new_email_marks_session_verified(self):
        from massageProject.accounts.booking_auth_views import SIGNUP_EMAIL_SESSION_KEY

        otp, code = EmailOTP.objects.create_for_email('newuser@example.com', EmailOTP.PURPOSE_SIGNUP)
        response = self.client.post(reverse('auth_verify_code'), {'email': 'newuser@example.com', 'code': code})
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['status'], 'verified')
        self.assertEqual(self.client.session.get(SIGNUP_EMAIL_SESSION_KEY), 'newuser@example.com')

    def test_correct_code_for_existing_active_user_logs_in(self):
        User.objects.create_user(email='existing@example.com', phone_number='0888940001', password='pass1234')
        otp, code = EmailOTP.objects.create_for_email('existing@example.com', EmailOTP.PURPOSE_LOGIN)
        response = self.client.post(reverse('auth_verify_code'), {'email': 'existing@example.com', 'code': code})
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['status'], 'logged_in')
        resp = self.client.get(reverse('profile_page'))
        self.assertTrue(resp.wsgi_request.user.is_authenticated)

    def test_correct_code_for_inactive_existing_user_is_blocked(self):
        user = User.objects.create_user(email='inactive@example.com', phone_number='0888940002', password='pass1234')
        user.is_active = False
        user.save(update_fields=['is_active'])
        otp, code = EmailOTP.objects.create_for_email('inactive@example.com', EmailOTP.PURPOSE_LOGIN)
        response = self.client.post(reverse('auth_verify_code'), {'email': 'inactive@example.com', 'code': code})
        data = response.json()
        self.assertFalse(data['success'])
        resp = self.client.get(reverse('profile_page'))
        self.assertFalse(resp.wsgi_request.user.is_authenticated)

    def test_wrong_code_is_rejected(self):
        EmailOTP.objects.create_for_email('a@example.com', EmailOTP.PURPOSE_SIGNUP)
        response = self.client.post(reverse('auth_verify_code'), {'email': 'a@example.com', 'code': '000000'})
        self.assertFalse(response.json()['success'])

    def test_no_code_requested_is_rejected(self):
        response = self.client.post(reverse('auth_verify_code'), {'email': 'never@example.com', 'code': '123456'})
        self.assertFalse(response.json()['success'])

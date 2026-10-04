from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from massageProject.accounts.forms import CustomAuthenticationForm
from massageProject.main_app.models import SiteConfiguration

User = get_user_model()


class LoginPasswordViewTest(TestCase):
    PASSWORD = 'ComplexPass!123'
    WRONG_PASSWORD = 'TotallyWrongPass!456'

    def setUp(self):
        cache.clear()

    def _create_user(self, email, phone_number, is_active):
        user = User.objects.create_user(email=email, phone_number=phone_number, password=self.PASSWORD)
        user.is_active = is_active
        user.save(update_fields=['is_active'])
        return user

    def test_active_user_correct_password_logs_in(self):
        self._create_user('active@example.com', '0888920001', is_active=True)
        response = self.client.post(reverse('auth_login_password'), {
            'email': 'active@example.com', 'password': self.PASSWORD,
        })
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['status'], 'logged_in')

    def test_inactive_user_correct_password_sees_custom_inactive_message(self):
        self._create_user('inactive@example.com', '0888920002', is_active=False)
        response = self.client.post(reverse('auth_login_password'), {
            'email': 'inactive@example.com', 'password': self.PASSWORD,
        })
        data = response.json()
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], str(CustomAuthenticationForm.error_messages['inactive']))

    def test_active_user_wrong_password_sees_generic_message_not_inactive_message(self):
        self._create_user('active2@example.com', '0888920003', is_active=True)
        response = self.client.post(reverse('auth_login_password'), {
            'email': 'active2@example.com', 'password': self.WRONG_PASSWORD,
        })
        data = response.json()
        self.assertFalse(data['success'])
        self.assertNotEqual(data['error'], str(CustomAuthenticationForm.error_messages['inactive']))

    def test_inactive_user_wrong_password_sees_generic_message_not_inactive_message(self):
        self._create_user('inactive2@example.com', '0888920004', is_active=False)
        response = self.client.post(reverse('auth_login_password'), {
            'email': 'inactive2@example.com', 'password': self.WRONG_PASSWORD,
        })
        data = response.json()
        self.assertFalse(data['success'])
        self.assertNotEqual(data['error'], str(CustomAuthenticationForm.error_messages['inactive']))

    def test_logged_in_session_is_established(self):
        self._create_user('sessioncheck@example.com', '0888920005', is_active=True)
        self.client.post(reverse('auth_login_password'), {
            'email': 'sessioncheck@example.com', 'password': self.PASSWORD,
        })
        response = self.client.get(reverse('profile_page'))
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_no_next_redirects_to_profile_when_booking_disabled(self):
        config = SiteConfiguration.get_solo()
        config.booking_enabled = False
        config.save()
        self._create_user('bookingoff@example.com', '0888920006', is_active=True)
        response = self.client.post(reverse('auth_login_password'), {
            'email': 'bookingoff@example.com', 'password': self.PASSWORD,
        })
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['redirect'], reverse('profile_page'))
        self.assertNotEqual(data['redirect'], reverse('reservation_page'))

    def test_no_next_redirects_to_reservation_when_booking_enabled(self):
        self._create_user('bookingon@example.com', '0888920007', is_active=True)
        response = self.client.post(reverse('auth_login_password'), {
            'email': 'bookingon@example.com', 'password': self.PASSWORD,
        })
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['redirect'], reverse('reservation_page'))

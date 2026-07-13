from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class CheckEmailViewTest(TestCase):
    def test_existing_email_returns_exists_true(self):
        User.objects.create_user(email='known@example.com', phone_number='0888800001', password='pass1234')
        response = self.client.post(reverse('auth_check_email'), {'email': 'known@example.com'})
        data = response.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['exists'])

    def test_unknown_email_returns_exists_false(self):
        response = self.client.post(reverse('auth_check_email'), {'email': 'unknown@example.com'})
        data = response.json()
        self.assertTrue(data['success'])
        self.assertFalse(data['exists'])

    def test_email_lookup_is_case_insensitive(self):
        User.objects.create_user(email='Mixed@Example.com', phone_number='0888800002', password='pass1234')
        response = self.client.post(reverse('auth_check_email'), {'email': 'mixed@example.com'})
        self.assertTrue(response.json()['exists'])

    def test_missing_email_is_rejected(self):
        response = self.client.post(reverse('auth_check_email'), {})
        self.assertEqual(response.status_code, 400)

    def test_get_is_not_allowed(self):
        response = self.client.get(reverse('auth_check_email'))
        self.assertEqual(response.status_code, 405)

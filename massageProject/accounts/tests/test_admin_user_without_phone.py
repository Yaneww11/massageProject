from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class AdminCreateUserWithoutPhoneTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            email='admin@example.com', phone_number='0888000001', password='AdminPass!123',
        )
        self.client.force_login(self.admin)

    def _add_user(self, email):
        return self.client.post(reverse('admin:accounts_customuser_add'), {
            'email': email,
            'first_name': '',
            'last_name': '',
            'phone_number': '',
            'usable_password': 'false',
        })

    def test_admin_can_create_user_without_phone_number(self):
        response = self._add_user('nophone@example.com')
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(User.objects.get(email='nophone@example.com').phone_number)

    def test_multiple_users_without_phone_number_can_coexist(self):
        self._add_user('nophone1@example.com')
        self._add_user('nophone2@example.com')
        self.assertEqual(User.objects.filter(phone_number__isnull=True).count(), 2)

from django.contrib.auth import authenticate, get_user_model
from django.test import TestCase

User = get_user_model()


class EmailLoginTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='login@example.com', phone_number='0888222222', password='pass1234',
        )

    def test_authenticate_by_email_succeeds(self):
        user = authenticate(email='login@example.com', password='pass1234')
        self.assertEqual(user, self.user)

    def test_authenticate_by_phone_number_fails(self):
        user = authenticate(phone_number='0888222222', password='pass1234')
        self.assertIsNone(user)

    def test_username_field_is_email(self):
        self.assertEqual(User.USERNAME_FIELD, 'email')
        self.assertEqual(User.REQUIRED_FIELDS, ['phone_number'])

from django.contrib.auth import get_user_model
from django.test import TestCase

from massageProject.accounts.forms import BookingRegistrationForm

User = get_user_model()


class BookingRegistrationFormTest(TestCase):
    VALID_DATA = {
        'first_name': 'Maria',
        'last_name': 'Ivanova',
        'phone_number': '0888900001',
        'password': 'ComplexPass!123',
    }

    def test_valid_data_creates_an_active_user_with_the_verified_email(self):
        form = BookingRegistrationForm(data=self.VALID_DATA, email='verified@example.com')
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.email, 'verified@example.com')
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password('ComplexPass!123'))

    def test_missing_email_is_invalid(self):
        form = BookingRegistrationForm(data=self.VALID_DATA, email=None)
        self.assertFalse(form.is_valid())

    def test_requires_first_and_last_name(self):
        data = {**self.VALID_DATA, 'first_name': '', 'last_name': ''}
        form = BookingRegistrationForm(data=data, email='verified2@example.com')
        self.assertFalse(form.is_valid())
        self.assertIn('first_name', form.errors)
        self.assertIn('last_name', form.errors)

    def test_date_of_birth_is_optional(self):
        form = BookingRegistrationForm(data=self.VALID_DATA, email='verified3@example.com')
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertIsNone(user.date_of_birth)

    def test_date_of_birth_can_be_provided(self):
        data = {**self.VALID_DATA, 'phone_number': '0888900002', 'date_of_birth': '1990-05-20'}
        form = BookingRegistrationForm(data=data, email='verified4@example.com')
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(str(user.date_of_birth), '1990-05-20')

    def test_phone_belonging_to_passwordless_user_is_claimed(self):
        existing = User.objects.create(email='placeholder@example.com', phone_number='0888900003')
        existing.set_unusable_password()
        existing.save()

        data = {**self.VALID_DATA, 'phone_number': '0888900003'}
        form = BookingRegistrationForm(data=data, email='claimed@example.com')
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.pk, existing.pk)
        self.assertEqual(user.email, 'claimed@example.com')
        self.assertTrue(user.check_password('ComplexPass!123'))

    def test_phone_belonging_to_a_user_with_a_password_is_rejected(self):
        User.objects.create_user(email='taken@example.com', phone_number='0888900004', password='pass1234')
        data = {**self.VALID_DATA, 'phone_number': '0888900004'}
        form = BookingRegistrationForm(data=data, email='new@example.com')
        self.assertFalse(form.is_valid())
        self.assertIn('phone_number', form.errors)

    def test_weak_password_is_rejected(self):
        data = {**self.VALID_DATA, 'phone_number': '0888900005', 'password': '123'}
        form = BookingRegistrationForm(data=data, email='weakpass@example.com')
        self.assertFalse(form.is_valid())
        self.assertIn('password', form.errors)

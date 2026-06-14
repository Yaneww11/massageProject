from django.test import TestCase
from massageProject.accounts.forms import CustomUserForm

class CustomUserFormTest(TestCase):
    def test_form_requires_first_and_last_name(self):
        # Data missing first_name and last_name
        data = {
            'phone_number': '0888123456',
            'email': 'test@example.com',
            'password1': 'ComplexPass!123',
            'password2': 'ComplexPass!123',
        }
        form = CustomUserForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('first_name', form.errors)
        self.assertIn('last_name', form.errors)

    def test_form_valid_with_names(self):
        data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'phone_number': '0888123456',
            'email': 'test@example.com',
            'password1': 'ComplexPass!123',
            'password2': 'ComplexPass!123',
        }
        form = CustomUserForm(data=data)
        self.assertTrue(form.is_valid())

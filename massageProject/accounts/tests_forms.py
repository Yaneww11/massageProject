from django.test import TestCase

from massageProject.accounts.forms import CustomAuthenticationForm


class CustomAuthenticationFormTest(TestCase):
    def test_username_field_labeled_for_email(self):
        form = CustomAuthenticationForm()
        self.assertEqual(form.fields['username'].label, 'Имейл')

    def test_no_phone_start_validation(self):
        form = CustomAuthenticationForm(data={'username': 'someone@example.com', 'password': 'x'})
        form.is_valid()
        self.assertNotIn('username', form.errors)

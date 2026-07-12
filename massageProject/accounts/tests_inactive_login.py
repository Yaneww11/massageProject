from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from massageProject.accounts.forms import CustomAuthenticationForm

User = get_user_model()


class InactiveUserLoginTest(TestCase):
    """
    Regression test: an unverified (is_active=False) user entering CORRECT
    credentials must see CustomAuthenticationForm's custom 'inactive' message
    (pointing them to resend-verification), not Django's generic invalid-login
    message. See CLAUDE.md task notes / bug report for full context.
    """

    PASSWORD = 'ComplexPass!123'
    WRONG_PASSWORD = 'TotallyWrongPass!456'

    def _create_user(self, email, phone_number, is_active):
        user = User.objects.create_user(
            email=email,
            phone_number=phone_number,
            password=self.PASSWORD,
        )
        user.is_active = is_active
        user.save(update_fields=['is_active'])
        return user

    def test_inactive_user_correct_password_sees_custom_inactive_message(self):
        # NOTE: asserted via response.context['form'], not response.content/assertContains.
        # templates/registration/login.html only loops over per-field form.errors and never
        # renders form.non_field_errors, so a non-field ValidationError (which is what
        # confirm_login_allowed() raises) never reaches the rendered HTML regardless of this
        # fix. That template gap is a separate, pre-existing bug outside this task's scope
        # (settings.py + this test file only) -- see report for details. Testing against the
        # bound form is the template-independent way to verify the *right* validation error
        # fired.
        self._create_user('inactive@example.com', '0888111111', is_active=False)

        response = self.client.post(reverse('login'), {
            'username': 'inactive@example.com',
            'password': self.PASSWORD,
        })

        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertIn(
            str(CustomAuthenticationForm.error_messages['inactive']),
            [str(e) for e in form.non_field_errors()],
        )

    def test_active_user_correct_password_logs_in(self):
        self._create_user('active@example.com', '0888222222', is_active=True)

        response = self.client.post(reverse('login'), {
            'username': 'active@example.com',
            'password': self.PASSWORD,
        })

        self.assertEqual(response.status_code, 302)

    def test_active_user_wrong_password_sees_generic_message_not_inactive_message(self):
        self._create_user('active2@example.com', '0888333333', is_active=True)

        response = self.client.post(reverse('login'), {
            'username': 'active2@example.com',
            'password': self.WRONG_PASSWORD,
        })

        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        errors = [str(e) for e in form.non_field_errors()]
        self.assertNotIn(str(CustomAuthenticationForm.error_messages['inactive']), errors)

    def test_inactive_user_wrong_password_sees_generic_message_not_inactive_message(self):
        self._create_user('inactive2@example.com', '0888444444', is_active=False)

        response = self.client.post(reverse('login'), {
            'username': 'inactive2@example.com',
            'password': self.WRONG_PASSWORD,
        })

        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        errors = [str(e) for e in form.non_field_errors()]
        self.assertNotIn(str(CustomAuthenticationForm.error_messages['inactive']), errors)

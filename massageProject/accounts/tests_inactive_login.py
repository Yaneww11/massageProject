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
        # NOTE: asserted via response.context['form'] rather than response.content.
        # This checks that the *right* validation error fired on the form,
        # independent of template rendering. See
        # test_inactive_user_correct_password_sees_message_in_rendered_html
        # below for the template-rendering regression guard (the template
        # previously never rendered form.non_field_errors, so this message
        # was computed correctly but invisible to users -- now fixed in
        # templates/registration/login.html).
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

    def test_inactive_user_correct_password_sees_message_in_rendered_html(self):
        # Regression guard for the template gap noted above: the message must
        # actually be present in response.content, not just attached to the
        # form object. templates/registration/login.html previously only
        # rendered per-field form.errors and never form.non_field_errors, so
        # this custom inactive-login message (a non-field error) was computed
        # correctly but never reached the rendered HTML.
        self._create_user('inactive3@example.com', '0888555555', is_active=False)

        response = self.client.post(reverse('login'), {
            'username': 'inactive3@example.com',
            'password': self.PASSWORD,
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            str(CustomAuthenticationForm.error_messages['inactive']),
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

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class InactiveUserLoginTest(TestCase):
    """
    Regression test: deactivating a logged-in user must invalidate their
    existing session on their very next request. The credential-flow
    variants of this test class (inactive user + correct/wrong password via
    the login view) moved to tests_login_password_view.py when the
    full-page login view was replaced by the auth modal's login-password/
    endpoint.
    """

    PASSWORD = 'ComplexPass!123'

    def _create_user(self, email, phone_number, is_active):
        user = User.objects.create_user(
            email=email,
            phone_number=phone_number,
            password=self.PASSWORD,
        )
        user.is_active = is_active
        user.save(update_fields=['is_active'])
        return user

    def test_deactivating_a_logged_in_user_invalidates_their_session(self):
        # Regression guard: AllowAllUsersModelBackend.get_user() always
        # returns True from user_can_authenticate(), so it kept resolving
        # request.user for is_active=False users on every subsequent
        # request -- meaning deactivating an account no longer killed the
        # user's existing session. The replacement backend must leave
        # get_user()/user_can_authenticate() untouched so deactivation still
        # invalidates the session on the very next request.
        user = self._create_user('deactivateme@example.com', '0888666666', is_active=True)

        logged_in = self.client.login(
            username='deactivateme@example.com', password=self.PASSWORD,
        )
        self.assertTrue(logged_in)

        response = self.client.get(reverse('profile_page'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.wsgi_request.user.is_authenticated)

        user.is_active = False
        user.save(update_fields=['is_active'])

        response = self.client.get(reverse('profile_page'))
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

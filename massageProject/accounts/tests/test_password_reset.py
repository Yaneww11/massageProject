import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class PasswordResetFlowTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='reset@example.com', phone_number='0888888001', password='OldPass!123',
        )

    def test_full_reset_round_trip(self):
        response = self.client.post(reverse('password_reset'), {'email': 'reset@example.com'})
        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)

        match = re.search(r'/accounts/reset/([\w-]+)/([\w-]+)/', mail.outbox[0].body)
        self.assertIsNotNone(match)
        uidb64, token = match.group(1), match.group(2)

        # First GET with the real token 302-redirects to a /set-password/ URL and
        # stashes the token in the session (Django's anti-referrer-leak behavior).
        confirm_url = reverse('password_reset_confirm', kwargs={'uidb64': uidb64, 'token': token})
        redirect_response = self.client.get(confirm_url)
        self.assertEqual(redirect_response.status_code, 302)
        set_password_url = redirect_response.url

        form_response = self.client.get(set_password_url)
        self.assertEqual(form_response.status_code, 200)
        self.assertTrue(form_response.context['validlink'])

        post_response = self.client.post(set_password_url, {
            'new_password1': 'BrandNewPass!456',
            'new_password2': 'BrandNewPass!456',
        })
        self.assertRedirects(post_response, reverse('password_reset_complete'))

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('BrandNewPass!456'))

    def test_unknown_email_does_not_send_mail_but_still_redirects(self):
        response = self.client.post(reverse('password_reset'), {'email': 'unknown@example.com'})
        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)

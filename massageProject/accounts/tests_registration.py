from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from massageProject.accounts.tokens import email_verification_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

User = get_user_model()


class RegistrationVerificationTest(TestCase):
    def test_registration_creates_inactive_user_and_sends_email(self):
        response = self.client.post(reverse('register'), {
            'first_name': 'Maria',
            'last_name': 'Ivanova',
            'phone_number': '0888444444',
            'email': 'maria@example.com',
            'password1': 'ComplexPass!123',
            'password2': 'ComplexPass!123',
        })
        self.assertRedirects(response, reverse('verification_sent'))

        user = User.objects.get(email='maria@example.com')
        self.assertFalse(user.is_active)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(user.email, mail.outbox[0].to)

    def test_valid_verification_link_activates_and_logs_in(self):
        user = User.objects.create_user(
            email='verify2@example.com', phone_number='0888555555', password='pass1234',
        )
        user.is_active = False
        user.save(update_fields=['is_active'])

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = email_verification_token_generator.make_token(user)
        response = self.client.get(reverse('verify_email', kwargs={'uidb64': uid, 'token': token}))

        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertEqual(response.status_code, 302)
        self.assertIn('_auth_user_id', self.client.session)

    def test_invalid_verification_link_does_not_activate(self):
        user = User.objects.create_user(
            email='verify3@example.com', phone_number='0888666666', password='pass1234',
        )
        user.is_active = False
        user.save(update_fields=['is_active'])

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        response = self.client.get(reverse('verify_email', kwargs={'uidb64': uid, 'token': 'garbage-token'}))

        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertEqual(response.status_code, 302)

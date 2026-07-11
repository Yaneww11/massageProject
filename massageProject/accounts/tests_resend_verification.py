from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class ResendVerificationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='resend@example.com', phone_number='0888777777', password='pass1234',
        )
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])

    def test_resend_sends_email_for_unverified_existing_email(self):
        response = self.client.post(reverse('resend_verification'), {'email': 'resend@example.com'})
        self.assertRedirects(response, reverse('verification_sent'))
        self.assertEqual(len(mail.outbox), 1)

    def test_resend_does_not_leak_whether_email_exists(self):
        response = self.client.post(reverse('resend_verification'), {'email': 'nobody@example.com'})
        self.assertRedirects(response, reverse('verification_sent'))
        self.assertEqual(len(mail.outbox), 0)

    def test_resend_does_nothing_for_already_active_user(self):
        self.user.is_active = True
        self.user.save(update_fields=['is_active'])
        response = self.client.post(reverse('resend_verification'), {'email': 'resend@example.com'})
        self.assertRedirects(response, reverse('verification_sent'))
        self.assertEqual(len(mail.outbox), 0)

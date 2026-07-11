from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, RequestFactory

from massageProject.accounts.emails import send_verification_email

User = get_user_model()


class SendVerificationEmailTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='newuser@example.com', phone_number='0888333333', password='pass1234',
            first_name='Ivan',
        )
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        self.factory = RequestFactory()

    def test_sends_one_email_with_html_alternative(self):
        request = self.factory.get('/')
        send_verification_email(request, self.user)

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.to, ['newuser@example.com'])
        self.assertEqual(len(sent.alternatives), 1)
        html_body, mimetype = sent.alternatives[0]
        self.assertEqual(mimetype, 'text/html')
        self.assertIn('http://testserver/', sent.body)
        self.assertIn('http://testserver/', html_body)

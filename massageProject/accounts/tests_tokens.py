from django.contrib.auth import get_user_model
from django.test import TestCase

from massageProject.accounts.tokens import email_verification_token_generator

User = get_user_model()


class EmailVerificationTokenGeneratorTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='verify@example.com', phone_number='0888111111', password='pass1234',
        )
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])

    def test_token_valid_for_unverified_user(self):
        token = email_verification_token_generator.make_token(self.user)
        self.assertTrue(email_verification_token_generator.check_token(self.user, token))

    def test_token_invalid_after_activation(self):
        token = email_verification_token_generator.make_token(self.user)
        self.user.is_active = True
        self.user.save(update_fields=['is_active'])
        self.assertFalse(email_verification_token_generator.check_token(self.user, token))

    def test_token_invalid_for_wrong_token_string(self):
        self.assertFalse(email_verification_token_generator.check_token(self.user, 'not-a-real-token'))

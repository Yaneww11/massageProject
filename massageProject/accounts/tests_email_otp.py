from django.test import TestCase
from django.utils import timezone

from massageProject.accounts.models import EmailOTP


class EmailOTPTest(TestCase):
    def test_create_for_email_returns_plaintext_code_but_stores_hash_only(self):
        otp, code = EmailOTP.objects.create_for_email('new@example.com', EmailOTP.PURPOSE_SIGNUP)
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())
        self.assertNotEqual(otp.code_hash, code)
        self.assertTrue(otp.check_code(code))

    def test_verify_with_correct_code_marks_consumed(self):
        otp, code = EmailOTP.objects.create_for_email('a@example.com', EmailOTP.PURPOSE_LOGIN)
        matched, error = EmailOTP.verify('a@example.com', code)
        self.assertIsNone(error)
        self.assertEqual(matched.pk, otp.pk)
        matched.refresh_from_db()
        self.assertIsNotNone(matched.consumed_at)

    def test_verify_with_wrong_code_increments_attempts_and_fails(self):
        EmailOTP.objects.create_for_email('b@example.com', EmailOTP.PURPOSE_LOGIN)
        matched, error = EmailOTP.verify('b@example.com', '000000')
        self.assertIsNone(matched)
        self.assertEqual(error, 'invalid_code')
        otp = EmailOTP.objects.live_for_email('b@example.com').first()
        self.assertEqual(otp.attempts, 1)

    def test_verify_with_no_code_sent_returns_no_code_error(self):
        matched, error = EmailOTP.verify('nocode@example.com', '123456')
        self.assertIsNone(matched)
        self.assertEqual(error, 'no_code')

    def test_expired_code_is_not_live(self):
        otp, code = EmailOTP.objects.create_for_email('c@example.com', EmailOTP.PURPOSE_SIGNUP)
        otp.expires_at = timezone.now() - timezone.timedelta(minutes=1)
        otp.save(update_fields=['expires_at'])
        matched, error = EmailOTP.verify('c@example.com', code)
        self.assertIsNone(matched)
        self.assertEqual(error, 'no_code')

    def test_code_becomes_dead_after_five_wrong_attempts(self):
        otp, code = EmailOTP.objects.create_for_email('d@example.com', EmailOTP.PURPOSE_SIGNUP)
        for _ in range(5):
            EmailOTP.verify('d@example.com', '000000')
        matched, error = EmailOTP.verify('d@example.com', code)
        self.assertIsNone(matched)
        self.assertEqual(error, 'no_code')

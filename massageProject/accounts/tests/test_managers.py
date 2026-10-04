from django.contrib.auth import get_user_model
from django.test import TestCase


class NormalizePhoneNumberTest(TestCase):
    def setUp(self):
        self.manager = get_user_model().objects

    def test_strips_leading_whitespace(self):
        self.assertEqual(self.manager.normalize_phone_number(' 0899123456'), '0899123456')

    def test_strips_trailing_whitespace(self):
        self.assertEqual(self.manager.normalize_phone_number('0899123456 '), '0899123456')

    def test_strips_and_converts_plus359(self):
        self.assertEqual(self.manager.normalize_phone_number(' +359891234567'), '0891234567')

    def test_no_whitespace_unchanged(self):
        self.assertEqual(self.manager.normalize_phone_number('0899123456'), '0899123456')

from unittest.mock import patch, Mock

import requests
from django.test import TestCase, override_settings

from massageProject.accounts.turnstile import verify_turnstile_token


@override_settings(TURNSTILE_SECRET_KEY='test-secret')
class VerifyTurnstileTokenTest(TestCase):
    def test_empty_token_fails_without_calling_api(self):
        with patch('massageProject.accounts.turnstile.requests.post') as mock_post:
            self.assertFalse(verify_turnstile_token(''))
            mock_post.assert_not_called()

    @patch('massageProject.accounts.turnstile.requests.post')
    def test_successful_verification_returns_true(self, mock_post):
        mock_post.return_value = Mock(json=lambda: {'success': True})
        self.assertTrue(verify_turnstile_token('good-token'))

    @patch('massageProject.accounts.turnstile.requests.post')
    def test_failed_verification_returns_false(self, mock_post):
        mock_post.return_value = Mock(json=lambda: {'success': False})
        self.assertFalse(verify_turnstile_token('bad-token'))

    @patch('massageProject.accounts.turnstile.requests.post')
    def test_network_error_returns_false(self, mock_post):
        mock_post.side_effect = requests.RequestException('boom')
        self.assertFalse(verify_turnstile_token('token'))

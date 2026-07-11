from unittest.mock import MagicMock, patch

from django.core.mail import EmailMultiAlternatives
from django.test import TestCase, override_settings
from googleapiclient.errors import HttpError

from massageProject.accounts.email_backend import GmailBackend


@override_settings(
    GMAIL_API_CLIENT_ID='test-client-id',
    GMAIL_API_CLIENT_SECRET='test-client-secret',
    GMAIL_API_REFRESH_TOKEN='test-refresh-token',
    GMAIL_API_USER_ID='me',
)
class GmailBackendTest(TestCase):
    def test_send_messages_returns_zero_for_empty_list(self):
        backend = GmailBackend()
        with patch('massageProject.accounts.email_backend.googleapiclient.discovery.build') as mock_build:
            result = backend.send_messages([])
        self.assertEqual(result, 0)
        mock_build.assert_not_called()

    def test_send_messages_sends_via_gmail_api(self):
        backend = GmailBackend()
        message = EmailMultiAlternatives('Subject', 'Body', 'from@example.com', ['to@example.com'])

        mock_service = MagicMock()
        mock_service.users.return_value.messages.return_value.send.return_value.execute.return_value = {'id': '123'}

        with patch('massageProject.accounts.email_backend.googleapiclient.discovery.build', return_value=mock_service) as mock_build:
            result = backend.send_messages([message])

        self.assertEqual(result, 1)
        mock_build.assert_called_once()
        mock_service.users.return_value.messages.return_value.send.assert_called_once()
        _, kwargs = mock_service.users.return_value.messages.return_value.send.call_args
        self.assertEqual(kwargs['userId'], 'me')
        self.assertIn('raw', kwargs['body'])

    def test_send_messages_raises_by_default_on_api_error(self):
        backend = GmailBackend()
        message = EmailMultiAlternatives('Subject', 'Body', 'from@example.com', ['to@example.com'])

        mock_service = MagicMock()
        mock_service.users.return_value.messages.return_value.send.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=500), content=b'error'
        )

        with patch('massageProject.accounts.email_backend.googleapiclient.discovery.build', return_value=mock_service):
            with self.assertRaises(HttpError):
                backend.send_messages([message])

    def test_send_messages_fails_silently_when_configured(self):
        backend = GmailBackend(fail_silently=True)
        message = EmailMultiAlternatives('Subject', 'Body', 'from@example.com', ['to@example.com'])

        mock_service = MagicMock()
        mock_service.users.return_value.messages.return_value.send.return_value.execute.side_effect = HttpError(
            resp=MagicMock(status=500), content=b'error'
        )

        with patch('massageProject.accounts.email_backend.googleapiclient.discovery.build', return_value=mock_service):
            result = backend.send_messages([message])

        self.assertEqual(result, 0)

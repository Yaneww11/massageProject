import base64

import google.oauth2.credentials
import googleapiclient.discovery
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from googleapiclient.errors import HttpError


class GmailBackend(BaseEmailBackend):
    def __init__(self, client_id=None, client_secret=None, refresh_token=None,
                 user_id=None, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.client_id = client_id or settings.GMAIL_API_CLIENT_ID
        self.client_secret = client_secret or settings.GMAIL_API_CLIENT_SECRET
        self.refresh_token = refresh_token or settings.GMAIL_API_REFRESH_TOKEN
        self.user_id = user_id or settings.GMAIL_API_USER_ID or 'me'
        self.service = None

    def open(self):
        if self.service is not None:
            return False

        try:
            credentials = google.oauth2.credentials.Credentials(
                'token',
                refresh_token=self.refresh_token,
                token_uri='https://accounts.google.com/o/oauth2/token',
                client_id=self.client_id,
                client_secret=self.client_secret,
            )
            self.service = googleapiclient.discovery.build(
                'gmail', 'v1', credentials=credentials, cache_discovery=False
            )
        except Exception:
            if not self.fail_silently:
                raise
            return None

        return True

    def close(self):
        self.service = None

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        opened_here = self.open()
        if not self.service or opened_here is None:
            # We failed silently on open().
            # Trying to send would be pointless.
            return 0

        sent_count = 0
        try:
            for message in email_messages:
                if self._send(message):
                    sent_count += 1
        finally:
            if opened_here:
                self.close()

        return sent_count

    def _send(self, email_message):
        raw_message = base64.urlsafe_b64encode(
            email_message.message().as_bytes()
        ).decode()
        try:
            self.service.users().messages().send(
                userId=self.user_id, body={'raw': raw_message}
            ).execute()
        except HttpError:
            if not self.fail_silently:
                raise
            return False
        return True

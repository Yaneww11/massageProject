from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/gmail.send']


class Command(BaseCommand):
    help = (
        'One-off helper: runs the Google OAuth consent flow locally and prints '
        'a refresh token to save as GMAIL_API_REFRESH_TOKEN in .env. Requires '
        'GMAIL_API_CLIENT_ID and GMAIL_API_CLIENT_SECRET to already be set in .env '
        '(created as a Desktop app OAuth client in Google Cloud Console).'
    )

    def add_arguments(self, parser):
        parser.add_argument('--client-id', required=False, help='Overrides GMAIL_API_CLIENT_ID from .env')
        parser.add_argument('--client-secret', required=False, help='Overrides GMAIL_API_CLIENT_SECRET from .env')

    def handle(self, *args, **options):
        client_id = options.get('client_id') or settings.GMAIL_API_CLIENT_ID
        client_secret = options.get('client_secret') or settings.GMAIL_API_CLIENT_SECRET

        if not client_id or not client_secret:
            raise CommandError(
                'Set GMAIL_API_CLIENT_ID and GMAIL_API_CLIENT_SECRET in .env first, '
                'or pass --client-id/--client-secret.'
            )

        client_config = {
            'installed': {
                'client_id': client_id,
                'client_secret': client_secret,
                'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                'token_uri': 'https://accounts.google.com/o/oauth2/token',
                'redirect_uris': ['http://localhost'],
            }
        }

        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        credentials = flow.run_local_server(port=0)

        self.stdout.write(self.style.SUCCESS('Authorization complete.'))
        self.stdout.write('Add this to your .env file:')
        self.stdout.write(f'GMAIL_API_REFRESH_TOKEN={credentials.refresh_token}')

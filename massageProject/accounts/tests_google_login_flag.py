from unittest.mock import MagicMock

from django.core.cache import cache
from django.test import TestCase

from massageProject.accounts.adapters import GoogleSocialAccountAdapter
from massageProject.main_app.models import SiteConfiguration


class GoogleLoginFlagAdapterTest(TestCase):
    def test_is_open_for_signup_true_when_flag_enabled(self):
        adapter = GoogleSocialAccountAdapter()
        sociallogin = MagicMock()
        self.assertTrue(adapter.is_open_for_signup(request=None, sociallogin=sociallogin))

    def test_is_open_for_signup_false_when_flag_disabled(self):
        config = SiteConfiguration.get_solo()
        config.google_login_enabled = False
        config.save()
        adapter = GoogleSocialAccountAdapter()
        sociallogin = MagicMock()
        self.assertFalse(adapter.is_open_for_signup(request=None, sociallogin=sociallogin))


class GoogleLoginFlagUITest(TestCase):
    def setUp(self):
        # The site_config context processor caches SiteConfiguration for 60s
        # (see main_app/context_processors.py); clear it so test order can't
        # leak a stale flag value between test methods within this class.
        cache.clear()

    def test_google_button_hidden_when_flag_disabled(self):
        config = SiteConfiguration.get_solo()
        config.google_login_enabled = False
        config.save()
        response = self.client.get('/bg/')
        content = response.content.decode()
        self.assertNotIn('auth-modal-google-btn', content)

    def test_google_button_present_when_flag_enabled(self):
        response = self.client.get('/bg/')
        content = response.content.decode()
        self.assertIn('auth-modal-google-btn', content)

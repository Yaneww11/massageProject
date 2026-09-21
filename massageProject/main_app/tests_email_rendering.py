from django.conf import settings
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import translation
from django.utils.translation import override

from massageProject.main_app.email_context import absolute_url, build_email, email_url, site_language
from massageProject.main_app.models import HomePage, SiteConfiguration


class RestoreLanguageMixin:
    """These tests deliberately activate other languages; translation.override()
    deactivates translations entirely on exit when none was active, which would
    leak into unrelated tests."""

    def tearDown(self):
        super().tearDown()
        translation.activate(settings.LANGUAGE_CODE)


@override_settings(SITE_URL='https://example.com')
class EmailLanguageTest(RestoreLanguageMixin, TestCase):
    """Emails used to render inside the triggering request, so a photographer
    browsing in English sent the client an English subject and an /en/ link."""

    def test_url_ignores_active_language(self):
        with override('en'):
            url = email_url('photo_proofing')

        with override(settings.LANGUAGE_CODE):
            expected = reverse('photo_proofing')

        self.assertEqual(url, f'https://example.com{expected}')
        self.assertNotIn('/en/', url)

    def test_subject_and_bodies_ignore_active_language(self):
        with override(settings.LANGUAGE_CODE):
            expected_subject = build_email('otp_email', 'a@example.com', {'code': '123456'}).subject

        with override('en'):
            message = build_email('otp_email', 'a@example.com', {'code': '123456'})

        self.assertEqual(message.subject, expected_subject)
        self.assertIn('123456', message.subject)

    def test_sending_does_not_switch_translations_off_afterwards(self):
        """Django's own translation.override() calls deactivate_all() on exit
        when nothing was active, which would silently untranslate whatever
        runs after a send."""
        translation.activate('en')
        with site_language():
            pass
        self.assertEqual(translation.get_language(), 'en')

        translation.deactivate_all()
        with site_language():
            pass
        self.assertEqual(translation.get_language(), settings.LANGUAGE_CODE)

    def test_link_in_rendered_body_has_no_english_prefix(self):
        with override('en'):
            message = build_email(
                'gallery_ready_email', 'a@example.com',
                {'client_name': 'Иван', 'review_url': email_url('photo_proofing')},
            )

        html = message.alternatives[0][0]
        self.assertIn('https://example.com', html)
        self.assertNotIn('/en/', html)


@override_settings(SITE_URL='https://example.com')
class EmailBrandingTest(RestoreLanguageMixin, TestCase):
    def test_ampersand_in_brand_name_is_not_double_escaped(self):
        homepage = HomePage.get_solo()
        homepage.brand_name = '<div>RenkArt &amp; Art</div>'
        homepage.save()

        self.assertEqual(homepage.brand_name_plain, 'RenkArt & Art')

        message = build_email('otp_email', 'a@example.com', {'code': '123456'})
        self.assertNotIn('&amp;amp;', message.alternatives[0][0])

    def test_theme_colors_reach_the_template(self):
        config = SiteConfiguration.get_solo()
        config.background_color = '#123456'
        config.primary_color = '#ABCDEF'
        config.accent_color = '#FEDCBA'
        config.save()

        html = build_email('otp_email', 'a@example.com', {'code': '123456'}).alternatives[0][0]

        self.assertIn('#123456', html)
        self.assertIn('#ABCDEF', html)
        self.assertIn('#FEDCBA', html)

    def test_reply_to_uses_configured_address_when_set(self):
        config = SiteConfiguration.get_solo()
        config.email_reply_to = 'studio@example.com'
        config.save()

        message = build_email('otp_email', 'a@example.com', {'code': '123456'})
        self.assertEqual(message.reply_to, ['studio@example.com'])

    def test_brand_name_is_taken_from_the_site_language(self):
        """brand_name is a modeltranslation field: looked up outside the
        override it follows the visitor, so the From header and footers would
        disagree with the bodies."""
        homepage = HomePage.get_solo()
        homepage.brand_name_bg = 'Студио БГ'
        homepage.brand_name_en = 'STUDIO EN'
        homepage.save()

        with override('en'):
            message = build_email('otp_email', 'a@example.com', {'code': '123456'})

        from email.header import decode_header, make_header

        sender = str(make_header(decode_header(message.from_email)))
        self.assertIn('Студио БГ', sender)
        self.assertIn('Студио БГ', message.body)
        self.assertNotIn('STUDIO EN', message.alternatives[0][0])

    def test_plain_text_part_is_not_html_escaped(self):
        """Autoescaping applies to .txt templates too, so an ampersand or a
        quote in the brand, signature or address leaks entities into the
        text/plain part."""
        homepage = HomePage.get_solo()
        homepage.brand_name = 'Relax & Health'
        homepage.save()
        config = SiteConfiguration.get_solo()
        config.email_signature = 'С поздрави, екипът на "Студио" & co'
        config.save()

        body = build_email('otp_email', 'a@example.com', {'code': '123456'}).body

        self.assertIn('Relax & Health', body)
        self.assertIn('"Студио" & co', body)
        self.assertNotIn('&amp;', body)
        self.assertNotIn('&quot;', body)

    def test_logo_url_handles_both_local_and_remote_media(self):
        """MEDIA_URL is a relative /media/ path in development and an absolute
        bucket URL in production; the emailed src must be absolute either way."""
        self.assertEqual(
            absolute_url('/media/branding/logo.png'),
            'https://example.com/media/branding/logo.png',
        )
        self.assertEqual(
            absolute_url('https://storage.googleapis.com/bucket/branding/logo.png'),
            'https://storage.googleapis.com/bucket/branding/logo.png',
        )

    def test_reply_to_is_empty_when_not_configured(self):
        message = build_email('otp_email', 'a@example.com', {'code': '123456'})
        self.assertEqual(message.reply_to, [])


@override_settings(SITE_URL='https://example.com')
class PasswordResetEmailTest(RestoreLanguageMixin, TestCase):
    def test_password_reset_email_renders_in_site_language_with_reply_to(self):
        from massageProject.accounts.models import CustomUser

        CustomUser.objects.create_user(
            email='client@example.com', phone_number='0888123456', password='pw12345678',
        )
        config = SiteConfiguration.get_solo()
        config.email_reply_to = 'studio@example.com'
        config.save()

        with override(settings.LANGUAGE_CODE):
            expected_subject = 'Заявка за нова парола'

        with override('en'):
            english_url = reverse('password_reset')

        response = self.client.post(english_url, {'email': 'client@example.com'}, HTTP_ACCEPT_LANGUAGE='en')

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.subject, expected_subject)
        self.assertEqual(message.reply_to, ['studio@example.com'])
        self.assertIn(response.status_code, (302, 200))

        # The reset link is the one emailed URL not built by email_url(), so it
        # needs its own language-leak assertion -- this request came in as English.
        html = message.alternatives[0][0]
        self.assertIn('href="http', html)
        self.assertIn('/accounts/reset/', html)
        self.assertNotIn('/en/accounts/reset/', html)

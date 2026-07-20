from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import translation

from massageProject.main_app.models import SiteConfiguration


class SiteConfigurationGetSoloTest(TestCase):
    def test_get_solo_creates_singleton_on_fresh_db(self):
        obj = SiteConfiguration.get_solo()
        self.assertIsInstance(obj, SiteConfiguration)
        self.assertEqual(obj.pk, 1)

    def test_get_solo_returns_same_instance_on_second_call(self):
        first = SiteConfiguration.get_solo()
        second = SiteConfiguration.get_solo()
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(SiteConfiguration.objects.count(), 1)

    def test_save_guard_prevents_second_instance(self):
        SiteConfiguration.get_solo()
        dupe = SiteConfiguration(pk=None, primary_color='#000000')
        dupe.save()
        self.assertEqual(SiteConfiguration.objects.count(), 1)


class SiteConfigurationDefaultsTest(TestCase):
    def test_defaults_match_current_spa_theme(self):
        obj = SiteConfiguration.get_solo()
        self.assertEqual(obj.primary_color, '#4A3728')
        self.assertEqual(obj.primary_light_color, '#6D5442')
        self.assertEqual(obj.secondary_color, '#C2A38E')
        self.assertEqual(obj.accent_color, '#8E735B')
        self.assertEqual(obj.background_color, '#FAF7F2')
        self.assertEqual(obj.text_color, '#2D241E')
        self.assertEqual(obj.text_muted_color, '#6B5E55')
        self.assertEqual(obj.font_pair, 'playfair_montserrat')
        self.assertEqual(obj.style_preset, 'soft')
        self.assertEqual(obj.hero_variant, 'split')
        self.assertEqual(obj.service_singular, 'услуга')
        self.assertEqual(obj.service_plural, 'услуги')
        self.assertEqual(obj.specialist_singular, 'специалист')
        self.assertEqual(obj.specialist_plural, 'специалисти')
        self.assertTrue(obj.booking_enabled)
        self.assertTrue(obj.comments_enabled)
        self.assertTrue(obj.google_login_enabled)

    def test_data_migration_seeds_row_without_get_solo(self):
        # No call to get_solo() here — proves the migration itself created pk=1.
        self.assertTrue(SiteConfiguration.objects.filter(pk=1).exists())


class SiteConfigurationValidationTest(TestCase):
    def test_invalid_hex_color_rejected(self):
        obj = SiteConfiguration.get_solo()
        obj.primary_color = 'not-a-color'
        with self.assertRaises(ValidationError):
            obj.full_clean()

    def test_valid_hex_color_accepted(self):
        obj = SiteConfiguration.get_solo()
        obj.primary_color = '#112233'
        obj.full_clean()  # must not raise


class SiteConfigurationTerminologyTranslationTest(TestCase):
    def test_terminology_fields_are_per_language(self):
        obj = SiteConfiguration.get_solo()
        obj.service_plural_bg = 'услуги'
        obj.service_plural_en = 'services'
        obj.save()

        obj.refresh_from_db()
        with translation.override('bg'):
            self.assertEqual(obj.service_plural, 'услуги')
        with translation.override('en'):
            self.assertEqual(obj.service_plural, 'services')

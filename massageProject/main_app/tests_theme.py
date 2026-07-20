from django.test import TestCase

from massageProject.main_app.models import SiteConfiguration
from massageProject.main_app.theme import FONT_PAIRS, STYLE_PRESETS


class ThemeDataTest(TestCase):
    def test_font_pairs_cover_every_model_choice(self):
        model_keys = {key for key, _ in SiteConfiguration.FONT_PAIR_CHOICES}
        self.assertEqual(set(FONT_PAIRS.keys()), model_keys)

    def test_style_presets_cover_every_model_choice(self):
        model_keys = {key for key, _ in SiteConfiguration.STYLE_PRESET_CHOICES}
        self.assertEqual(set(STYLE_PRESETS.keys()), model_keys)

    def test_every_font_pair_has_required_keys(self):
        for key, pair in FONT_PAIRS.items():
            self.assertIn('google_fonts_url', pair, key)
            self.assertIn('heading_family', pair, key)
            self.assertIn('body_family', pair, key)

    def test_every_style_preset_has_required_keys(self):
        for key, preset in STYLE_PRESETS.items():
            for var in ('radius_sm', 'radius_md', 'radius_lg', 'shadow_sm', 'shadow_md', 'shadow_lg'):
                self.assertIn(var, preset, key)

    def test_soft_preset_matches_current_variables_css_defaults(self):
        soft = STYLE_PRESETS['soft']
        self.assertEqual(soft['radius_sm'], '4px')
        self.assertEqual(soft['radius_md'], '8px')
        self.assertEqual(soft['radius_lg'], '16px')
        self.assertEqual(soft['shadow_sm'], '0 2px 4px rgba(0,0,0,0.05)')
        self.assertEqual(soft['shadow_md'], '0 4px 12px rgba(0,0,0,0.1)')
        self.assertEqual(soft['shadow_lg'], '0 10px 25px rgba(0,0,0,0.15)')

    def test_default_font_pair_matches_current_variables_css_import(self):
        default = FONT_PAIRS['playfair_montserrat']
        self.assertIn('Playfair+Display', default['google_fonts_url'])
        self.assertIn('Montserrat', default['google_fonts_url'])
        self.assertEqual(default['heading_family'], "'Playfair Display', serif")
        self.assertEqual(default['body_family'], "'Montserrat', sans-serif")

from django.test import TestCase
from django.template import Context, Template

from massageProject.main_app.models import SiteConfiguration
from massageProject.main_app.theme import (
    FONT_PAIRS, STYLE_PRESETS, COLOR_PRESETS, on_color, contrast_ratio,
)


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


class OnColorHelperTest(TestCase):
    def test_white_background_gets_black_text(self):
        self.assertEqual(on_color('#FFFFFF'), '#000000')

    def test_black_background_gets_white_text(self):
        self.assertEqual(on_color('#000000'), '#FFFFFF')

    def test_mid_gray_boundary(self):
        # #767676 sits right around the WCAG luminance threshold used by on_color.
        result = on_color('#767676')
        self.assertIn(result, ('#000000', '#FFFFFF'))


class ContrastRatioHelperTest(TestCase):
    def test_black_on_white_is_max_contrast(self):
        self.assertAlmostEqual(contrast_ratio('#FFFFFF', '#000000'), 21, places=0)

    def test_identical_colors_have_contrast_of_one(self):
        self.assertAlmostEqual(contrast_ratio('#4A3728', '#4A3728'), 1, places=5)

    def test_order_of_arguments_does_not_matter(self):
        self.assertAlmostEqual(
            contrast_ratio('#FAF7F2', '#2D241E'), contrast_ratio('#2D241E', '#FAF7F2'), places=5,
        )


class ColorPresetsDataTest(TestCase):
    def test_color_presets_cover_every_non_custom_model_choice(self):
        model_keys = {key for key, _ in SiteConfiguration.COLOR_PRESET_CHOICES if key != 'custom'}
        self.assertEqual(set(COLOR_PRESETS.keys()), model_keys)

    COLOR_FIELDS = (
        'primary_color', 'primary_light_color', 'secondary_color', 'accent_color',
        'background_color', 'text_color', 'text_muted_color', 'border_color',
    )

    def test_every_preset_has_all_color_fields_and_a_label(self):
        for key, preset in COLOR_PRESETS.items():
            self.assertIn('label', preset, key)
            for field in self.COLOR_FIELDS:
                self.assertIn(field, preset, f'{key}.{field}')

    def test_every_preset_backgrounds_pass_contrast_against_their_on_color(self):
        for key, preset in COLOR_PRESETS.items():
            for field in ('primary_color', 'primary_light_color', 'secondary_color', 'accent_color'):
                bg = preset[field]
                ratio = contrast_ratio(bg, on_color(bg))
                self.assertGreaterEqual(ratio, 4.5, f'{key}.{field}={bg} contrast={ratio:.2f}')


class ThemeTemplateFiltersTest(TestCase):
    def test_font_pair_info_filter_returns_matching_dict(self):
        # dict lookup via dot-notation in a template requires the filter's
        # return value to support attribute/key access, which plain dicts do
        rendered = Template(
            "{% load theme_extras %}{% with pair='playfair_montserrat'|font_pair_info %}{{ pair.heading_family }}{% endwith %}"
        ).render(Context({}))
        self.assertEqual(rendered, "'Playfair Display', serif")

    def test_font_pair_info_unknown_key_falls_back_to_default(self):
        rendered = Template(
            "{% load theme_extras %}{% with pair='not-a-real-key'|font_pair_info %}{{ pair.heading_family }}{% endwith %}"
        ).render(Context({}))
        self.assertEqual(rendered, "'Playfair Display', serif")

    def test_style_preset_vars_filter_returns_matching_dict(self):
        rendered = Template(
            "{% load theme_extras %}{% with preset='sharp'|style_preset_vars %}{{ preset.radius_sm }}{% endwith %}"
        ).render(Context({}))
        self.assertEqual(rendered, '0px')

    def test_style_preset_vars_unknown_key_falls_back_to_soft(self):
        rendered = Template(
            "{% load theme_extras %}{% with preset='not-a-real-key'|style_preset_vars %}{{ preset.radius_sm }}{% endwith %}"
        ).render(Context({}))
        self.assertEqual(rendered, '4px')

    def test_on_color_vars_filter_derives_from_site_config(self):
        config = SiteConfiguration.get_solo()
        rendered = Template(
            "{% load theme_extras %}{% with oc=site_config|on_color_vars %}{{ oc.on_primary }}{% endwith %}"
        ).render(Context({'site_config': config}))
        self.assertEqual(rendered, on_color(config.primary_color))


class ThemeOverridesRenderingTest(TestCase):
    def test_home_page_includes_theme_colors_and_font_link(self):
        response = self.client.get('/bg/')
        content = response.content.decode()
        self.assertIn('--primary-color: #4A3728', content)
        self.assertIn('--on-primary: #FFFFFF', content)
        self.assertIn('--on-primary-light: #FFFFFF', content)
        self.assertIn('--on-secondary: #000000', content)
        self.assertIn('--on-accent: #000000', content)
        self.assertIn('--font-heading: \'Playfair Display\', serif', content)
        self.assertIn('fonts.googleapis.com/css2?family=Playfair+Display', content)

    def test_variables_css_no_longer_hardcodes_google_fonts_import(self):
        with open('staticfiles/css/base/variables.css') as f:
            content = f.read()
        self.assertNotIn('@import url(\'https://fonts.googleapis.com', content)


class HeroVariantSelectionTest(TestCase):
    def test_home_page_renders_split_hero_by_default(self):
        response = self.client.get('/bg/')
        content = response.content.decode()
        self.assertIn('hp-hero-inner', content)
        self.assertIn('home_background.jpg', content)


class CarouselHeroVariantTest(TestCase):
    def test_carousel_variant_renders_when_selected(self):
        config = SiteConfiguration.get_solo()
        config.hero_variant = 'carousel'
        config.save()
        try:
            response = self.client.get('/bg/')
            content = response.content.decode()
            self.assertIn('hp-hero-carousel', content)
            self.assertNotIn('hp-hero-inner', content)
        finally:
            config.hero_variant = 'split'
            config.save()


class FullbleedHeroVariantTest(TestCase):
    def test_fullbleed_variant_renders_when_selected(self):
        config = SiteConfiguration.get_solo()
        config.hero_variant = 'fullbleed'
        config.save()
        try:
            response = self.client.get('/bg/')
            content = response.content.decode()
            self.assertIn('hp-hero-fullbleed', content)
            self.assertNotIn('hp-hero-inner', content)
        finally:
            config.hero_variant = 'split'
            config.save()

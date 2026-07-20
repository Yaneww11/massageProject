from django.test import TestCase


class FooterBrandingTest(TestCase):
    def test_footer_copyright_uses_dynamic_brand_name_not_hardcoded_text(self):
        response = self.client.get('/bg/')
        content = response.content.decode()
        self.assertNotIn('Масажно студио Сияние', content)
        self.assertIn('Relax &amp; Health', content)  # demo HomePage.brand_name default


class HeroBrandingTest(TestCase):
    def test_hero_eyebrow_does_not_say_massage_studio(self):
        response = self.client.get('/bg/')
        content = response.content.decode()
        self.assertNotIn('Масажно студио · от 2014', content)
        self.assertIn('Нашето студио · от 2014', content)

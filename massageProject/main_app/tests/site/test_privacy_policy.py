from django.test import TestCase
from django.urls import reverse

from massageProject.main_app.models import Gallery, HomePage


class PrivacyPolicySanitizationTest(TestCase):
    """B03 — privacy policy content is sanitised, not rendered raw."""

    def test_script_is_stripped_and_formatting_kept(self):
        gallery = Gallery.objects.create(gallery_type=Gallery.TYPE_HOMEPAGE, title='g')
        HomePage.objects.create(
            brand_name='Studio',
            description='desc',
            gallery=gallery,
            privacy_policy_content=(
                '<script>alert("B03")</script>'
                '<div style="color: #555;"><h3>Title</h3><p onclick="evil()">Text</p></div>'
            )
        )
        response = self.client.get(reverse('privacy_policy'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertNotIn('<script>alert("B03")</script>', html)
        self.assertNotIn('onclick', html)
        self.assertIn('<h3>Title</h3>', html)
        self.assertIn('<div style="color: #555;">', html)

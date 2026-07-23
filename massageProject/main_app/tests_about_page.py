from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from massageProject.main_app.models import BusinessInfo


class BusinessInfoJsonFieldsTest(TestCase):
    def test_new_fields_default_empty(self):
        info = BusinessInfo.objects.create(description="Test Studio")
        self.assertEqual(info.stats, {})
        self.assertEqual(info.credentials, {})
        self.assertEqual(info.faq, [])

    def test_fields_round_trip(self):
        info = BusinessInfo.objects.create(
            description="Test Studio",
            stats={"years_of_practice": "8+", "clients_served": "500+"},
            credentials={"training": [{"title": "Swedish Massage", "subtitle": "Vienna Institute", "year": "2019", "description": "..."}], "recognition": []},
            faq=[{"question": "Do you take walk-ins?", "answer": "No, by appointment only."}],
        )
        info.refresh_from_db()
        self.assertEqual(info.stats["years_of_practice"], "8+")
        self.assertEqual(info.credentials["training"][0]["title"], "Swedish Massage")
        self.assertEqual(info.faq[0]["question"], "Do you take walk-ins?")


class AboutPageContextTest(TestCase):
    def setUp(self):
        dummy_image = SimpleUploadedFile(name='studio.jpg', content=b'', content_type='image/jpeg')
        BusinessInfo.objects.create(description="Reneta's studio.", main_image=dummy_image)

    def test_about_page_has_no_specialist_context(self):
        response = self.client.get(reverse('about_page'))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('specialist', response.context)

    def test_about_page_business_info_is_full_instance(self):
        response = self.client.get(reverse('about_page'))
        self.assertIsInstance(response.context['business_info'], BusinessInfo)
        self.assertEqual(response.context['business_info'].description, "Reneta's studio.")

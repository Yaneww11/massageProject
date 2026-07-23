from django.test import TestCase
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

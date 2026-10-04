from django.test import TestCase
from massageProject.main_app.models import HomePage


class HomePageGetSoloTest(TestCase):
    def test_get_solo_creates_singleton_on_fresh_db(self):
        obj = HomePage.get_solo()
        self.assertIsInstance(obj, HomePage)

    def test_get_solo_returns_same_instance_on_second_call(self):
        first = HomePage.get_solo()
        second = HomePage.get_solo()
        self.assertEqual(first.pk, second.pk)

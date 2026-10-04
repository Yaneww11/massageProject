from django.test import TestCase
from django.urls import reverse

from massageProject.main_app.models import Service


class FeaturedServicesOrderTest(TestCase):
    def _service(self, name, home_page=True):
        return Service.objects.create(
            name=name, price=10, duration_in_minutes=30,
            short_description='x', home_page=home_page,
        )

    def test_most_recently_updated_featured_service_comes_first(self):
        a = self._service('A')
        b = self._service('B')
        c = self._service('C')
        self._service('Hidden', home_page=False)

        a.save()  # touching A moves it to the front

        response = self.client.get(reverse('index'))
        self.assertEqual(response.context['services'], [a, c, b])

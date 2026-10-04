from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from massageProject.main_app.tests.helpers import BugFixTestBase


class AvailabilityAuthTest(BugFixTestBase):
    """B07 — check_availability must require authentication."""

    def _url(self):
        date_str = (timezone.localdate() + timedelta(days=3)).strftime('%Y-%m-%d')
        return (
            reverse('check_availability')
            + f'?specialist_id={self.specialist.pk}&date={date_str}&service_id={self.service.pk}'
        )

    def test_anonymous_is_redirected(self):
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 302)

    def test_authenticated_gets_slots(self):
        self.login()
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertIn('slots', response.json())

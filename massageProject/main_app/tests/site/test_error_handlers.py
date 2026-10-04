from django.urls import reverse

from massageProject.main_app.tests.helpers import BugFixTestBase


class Missing404HandlerTest(BugFixTestBase):
    """B08 — nonexistent PKs must return 404, not 500."""

    def test_edit_reservation_unknown_pk_returns_404(self):
        self.login()
        response = self.client.get(reverse('edit_reservation', kwargs={'pk': 99999}))
        self.assertEqual(response.status_code, 404)

    def test_delete_reservation_unknown_pk_returns_404(self):
        self.login()
        response = self.client.get(reverse('delete_reservation', kwargs={'pk': 99999}))
        self.assertEqual(response.status_code, 404)

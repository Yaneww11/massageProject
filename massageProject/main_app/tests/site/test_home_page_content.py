from django.urls import reverse

from massageProject.main_app.tests.helpers import BugFixTestBase


class HomeReviewButtonTest(BugFixTestBase):
    """B12 — the review button opens the auth modal for anonymous visitors."""

    def test_anonymous_gets_auth_modal_trigger(self):
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertNotIn('id="hp-open-modal"', html)
        self.assertIn('data-auth-modal-trigger', html)

    def test_authenticated_gets_review_modal_button(self):
        self.login()
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="hp-open-modal"', response.content.decode())


class ServicesJsonEmbeddingTest(BugFixTestBase):
    """B04 — services data must be embedded via json_script, not |safe."""

    def test_script_breakout_is_escaped(self):
        self.service.name = 'Test</script><script>alert("B04")</script>'
        self.service.save()
        self.login()
        response = self.client.get(reverse('reservation_page'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('id="services-data"', html)
        self.assertNotIn('</script><script>alert', html)
        # The payload survives as data after HTML-entity escaping.
        self.assertIn('\\u003C/script\\u003E', html)

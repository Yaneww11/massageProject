import json
from datetime import time, timedelta

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from massageProject.accounts.models import CustomUser
from massageProject.main_app.models import (
    Comment, Gallery, HomePage, Service, Specialist, Reservation,
    WorkingHours,
)


class BugFixTestBase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.user = CustomUser.objects.create_user(
            phone_number='0888888888',
            email='test@example.com',
            password='password123',
            first_name='John',
            last_name='Doe',
        )
        self.service = Service.objects.create(
            name='Relax Service',
            description='desc',
            price=50.00,
            duration_in_minutes=60,
            short_description='short',
        )
        self.specialist = Specialist.objects.create(
            name='John Doe',
            description='expert',
            phone_number='0888888889',
            email='john@example.com',
        )
        for i in range(7):
            WorkingHours.objects.create(
                specialist=self.specialist,
                day_of_week=i,
                start_time=time(9, 0),
                end_time=time(17, 0),
            )

    def login(self):
        self.client.force_login(self.user)


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


class Missing404HandlerTest(BugFixTestBase):
    """B08 — nonexistent PKs must return 404, not 500."""

    def test_service_detail_unknown_pk_returns_404(self):
        response = self.client.get(reverse('service_detail', kwargs={'pk': 99999}))
        self.assertEqual(response.status_code, 404)

    def test_edit_reservation_unknown_pk_returns_404(self):
        self.login()
        response = self.client.get(reverse('edit_reservation', kwargs={'pk': 99999}))
        self.assertEqual(response.status_code, 404)

    def test_delete_reservation_unknown_pk_returns_404(self):
        self.login()
        response = self.client.get(reverse('delete_reservation', kwargs={'pk': 99999}))
        self.assertEqual(response.status_code, 404)


class SubmitCommentAuthTest(BugFixTestBase):
    """B12 — submit_comment requires login; author always from the account."""

    def test_anonymous_post_is_redirected_and_saves_nothing(self):
        response = self.client.post(
            reverse('submit_comment'),
            {'content': 'Great service', 'author': 'Fake Person', 'rating': 5},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Comment.objects.count(), 0)

    def test_author_param_is_ignored_for_authenticated_user(self):
        self.login()
        response = self.client.post(
            reverse('submit_comment'),
            {'content': 'Great service', 'author': 'Fake Person', 'rating': 5},
        )
        self.assertEqual(response.status_code, 200)
        comment = Comment.objects.get()
        self.assertEqual(comment.author, 'John Doe')
        self.assertEqual(comment.user, self.user)


class SubmitCommentRateLimitTest(BugFixTestBase):
    """B09 — one comment per IP per 60 seconds."""

    def test_second_rapid_post_gets_429(self):
        self.login()
        first = self.client.post(
            reverse('submit_comment'), {'content': 'First', 'rating': 5}
        )
        self.assertEqual(first.status_code, 200)
        second = self.client.post(
            reverse('submit_comment'), {'content': 'Second', 'rating': 5}
        )
        self.assertEqual(second.status_code, 429)
        self.assertEqual(Comment.objects.count(), 1)

    def test_post_succeeds_after_cooldown(self):
        self.login()
        self.client.post(reverse('submit_comment'), {'content': 'First', 'rating': 5})
        cache.clear()  # simulate the cooldown window passing
        response = self.client.post(
            reverse('submit_comment'), {'content': 'Second', 'rating': 5}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Comment.objects.count(), 2)


class OversizedPayloadTest(BugFixTestBase):
    """B10 — comment content and reservation additional_text are bounded."""

    def test_oversized_comment_rejected(self):
        self.login()
        response = self.client.post(
            reverse('submit_comment'), {'content': 'x' * 2001, 'rating': 5}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Comment.objects.count(), 0)

    def test_comment_at_limit_accepted(self):
        self.login()
        response = self.client.post(
            reverse('submit_comment'), {'content': 'x' * 2000, 'rating': 5}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Comment.objects.count(), 1)

    def test_oversized_additional_text_fails_validation(self):
        future = timezone.localtime(timezone.now()) + timedelta(days=3)
        reservation = Reservation(
            user=self.user,
            service=self.service,
            specialist=self.specialist,
            date=future.date(),
            time=time(10, 0),
            additional_text='x' * 501,
        )
        with self.assertRaises(ValidationError):
            reservation.full_clean()


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


class PrivacyPolicySanitizationTest(TestCase):
    """B03 — privacy policy content is sanitised, not rendered raw."""

    def test_script_is_stripped_and_formatting_kept(self):
        gallery = Gallery.objects.create(title='g')
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


class MassagesJsonEmbeddingTest(BugFixTestBase):
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

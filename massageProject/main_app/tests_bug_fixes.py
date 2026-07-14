import json
from datetime import time, timedelta

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from massageProject.accounts.models import CustomUser
from massageProject.main_app.models import (
    Comment, Massage, Masseur, MessageReservation, WorkingHours,
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
        self.massage = Massage.objects.create(
            name='Relax Massage',
            description='desc',
            price=50.00,
            duration_in_minutes=60,
            short_description='short',
        )
        self.masseur = Masseur.objects.create(
            name='John Doe',
            description='expert',
            phone_number='0888888889',
            email='john@example.com',
        )
        for i in range(7):
            WorkingHours.objects.create(
                masseur=self.masseur,
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
            + f'?masseur_id={self.masseur.pk}&date={date_str}&massage_id={self.massage.pk}'
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

    def test_massage_detail_unknown_pk_returns_404(self):
        response = self.client.get(reverse('massage_detail', kwargs={'pk': 99999}))
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
            {'content': 'Great massage', 'author': 'Fake Person', 'rating': 5},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Comment.objects.count(), 0)

    def test_author_param_is_ignored_for_authenticated_user(self):
        self.login()
        response = self.client.post(
            reverse('submit_comment'),
            {'content': 'Great massage', 'author': 'Fake Person', 'rating': 5},
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
        reservation = MessageReservation(
            user=self.user,
            massage=self.massage,
            masseur=self.masseur,
            date=future.date(),
            time=time(10, 0),
            additional_text='x' * 501,
        )
        with self.assertRaises(ValidationError):
            reservation.full_clean()


class MassagesJsonEmbeddingTest(BugFixTestBase):
    """B04 — massages data must be embedded via json_script, not |safe."""

    def test_script_breakout_is_escaped(self):
        self.massage.name = 'Test</script><script>alert("B04")</script>'
        self.massage.save()
        self.login()
        response = self.client.get(reverse('reservation_page'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('id="massages-data"', html)
        self.assertNotIn('</script><script>alert', html)
        # The payload survives as data after HTML-entity escaping.
        self.assertIn('\\u003C/script\\u003E', html)

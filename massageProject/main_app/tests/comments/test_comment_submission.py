from datetime import time, timedelta

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from massageProject.main_app.models import Comment, Reservation
from massageProject.main_app.tests.helpers import BugFixTestBase


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

    def test_user_without_name_is_refused_and_email_never_becomes_author(self):
        self.user.first_name = ''
        self.user.last_name = ''
        self.user.phone_number = None
        self.user.save()
        self.login()
        response = self.client.post(
            reverse('submit_comment'), {'content': 'Great service', 'rating': 5}
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])
        self.assertEqual(Comment.objects.count(), 0)


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

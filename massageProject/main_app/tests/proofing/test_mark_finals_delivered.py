from django.core import mail
from django.test import override_settings
from django.urls import reverse

from massageProject.main_app.models import Reservation
from massageProject.main_app.tests.proofing.test_final_zip_delivery import FinalZipBase


@override_settings(IS_PHOTOGRAPHER_WEBSITE=True)
class MarkFinalsDeliveredTest(FinalZipBase):
    def setUp(self):
        super().setUp()
        self.url = reverse('mark_finals_delivered', args=[self.reservation.pk])

    def _delivered(self):
        self.reservation.refresh_from_db()
        return self.reservation.finals_delivered_at

    def test_assigned_specialist_stamps_without_email(self):
        response = self.http.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(self._delivered())
        self.assertEqual(len(mail.outbox), 0)

    def test_staff_can_stamp(self):
        self.http.force_login(self.staff_user)
        self.http.post(self.url)
        self.assertIsNotNone(self._delivered())

    def test_works_when_client_has_no_email(self):
        self.client_user.email = ''
        self.client_user.save()
        self.http.post(self.url)
        self.assertIsNotNone(self._delivered())

    def test_other_specialist_and_client_denied(self):
        for user in (self.other_user, self.client_user):
            self.http.force_login(user)
            self.assertIn(self.http.post(self.url).status_code, (403, 404))
        self.assertIsNone(self._delivered())

    def test_get_not_allowed(self):
        self.assertEqual(self.http.get(self.url).status_code, 405)
        self.assertIsNone(self._delivered())

    def test_photographer_mode_off_is_inert(self):
        with override_settings(IS_PHOTOGRAPHER_WEBSITE=False):
            self.assertEqual(self.http.post(self.url).status_code, 404)
        self.assertIsNone(self._delivered())

    def test_unfinalized_proofing_stamps_nothing(self):
        Reservation.objects.filter(pk=self.reservation.pk).update(proofing_finalized_at=None)
        response = self.http.post(self.url, follow=True)
        self.assertIsNone(self._delivered())
        self.assertTrue(list(response.context['messages']))

    def test_already_delivered_keeps_original_stamp(self):
        self.http.post(self.url)
        first = self._delivered()
        self.http.post(self.url)
        self.assertEqual(self._delivered(), first)

    def test_redirect_keeps_page_and_filters(self):
        response = self.http.post(self.url, {'return_query': 'phase=all&page=2'})
        self.assertEqual(response.url, reverse('profile_page') + '?phase=all&page=2')

    def test_redirect_ignores_non_query_garbage(self):
        response = self.http.post(self.url, {'return_query': '//evil.com'})
        self.assertTrue(response.url.startswith(reverse('profile_page')))
        self.assertNotIn('evil.com', response.url.split('?')[0])


@override_settings(IS_PHOTOGRAPHER_WEBSITE=True)
class MarkFinalsDeliveredButtonTest(FinalZipBase):
    def _table(self):
        return self.http.get(reverse('profile_page') + '?phase=all').content.decode()

    def test_button_shown_when_finalized_and_not_delivered(self):
        html = self._table()
        self.assertIn('Маркирай като предадени', html)
        self.assertIn(reverse('mark_finals_delivered', args=[self.reservation.pk]), html)

    def test_button_shown_without_client_email(self):
        self.client_user.email = ''
        self.client_user.save()
        self.assertIn(reverse('mark_finals_delivered', args=[self.reservation.pk]), self._table())

    def test_button_hidden_after_delivery(self):
        self.http.post(reverse('mark_finals_delivered', args=[self.reservation.pk]))
        self.assertNotIn(reverse('mark_finals_delivered', args=[self.reservation.pk]), self._table())
        self.assertIn('Изпрати отново', self._table())

    def test_button_hidden_when_not_finalized(self):
        Reservation.objects.filter(pk=self.reservation.pk).update(proofing_finalized_at=None)
        self.assertNotIn(reverse('mark_finals_delivered', args=[self.reservation.pk]), self._table())

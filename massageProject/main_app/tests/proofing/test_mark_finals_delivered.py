from datetime import time as time_cls, timedelta

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from massageProject.accounts.models import CustomUser
from massageProject.main_app.models import Reservation, Service, Specialist


class FinalsDeliveredBase(TestCase):
    def setUp(self):
        ct = ContentType.objects.get_for_model(Reservation)
        view_all = Permission.objects.get(content_type=ct, codename='view_all_reservations')
        view_specialist = Permission.objects.get(content_type=ct, codename='view_specialist_reservations')
        self.service = Service.objects.create(
            name='Photoshoot', description='d', price=100, duration_in_minutes=60, short_description='s',
        )
        self.specialist_user = CustomUser.objects.create_user(
            phone_number='0888400001', email='sp@example.com', password='pass12345',
        )
        self.specialist = Specialist.objects.create(
            name='Ivan', description='d', phone_number='0888400002', email='ivan@example.com',
            user=self.specialist_user,
        )
        self.specialist_user.user_permissions.add(view_specialist)
        self.other_user = CustomUser.objects.create_user(
            phone_number='0888400006', email='other@example.com', password='pass12345',
        )
        self.other_user.user_permissions.add(view_specialist)
        Specialist.objects.create(
            name='Zora', description='d', phone_number='0888400007', email='z@example.com', user=self.other_user,
        )
        self.staff_user = CustomUser.objects.create_user(
            phone_number='0888400004', email='staff@example.com', password='pass12345',
        )
        self.staff_user.user_permissions.add(view_all)
        self.client_user = CustomUser.objects.create_user(
            phone_number='0888400005', email='client@example.com', password='pass12345',
        )
        candidate = timezone.localdate() - timedelta(days=3)
        while candidate.weekday() != 0:
            candidate -= timedelta(days=1)
        self.reservation = Reservation.objects.create(
            user=self.client_user, service=self.service, specialist=self.specialist,
            date=candidate, time=time_cls(10, 0), status=Reservation.STATUS_COMPLETED,
        )
        self.reservation.finalize_proofing()
        self.http = Client()
        self.http.force_login(self.specialist_user)


@override_settings(IS_PHOTOGRAPHER_WEBSITE=True)
class MarkFinalsDeliveredTest(FinalsDeliveredBase):
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
class MarkFinalsDeliveredButtonTest(FinalsDeliveredBase):
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

    def test_button_hidden_when_not_finalized(self):
        Reservation.objects.filter(pk=self.reservation.pk).update(proofing_finalized_at=None)
        self.assertNotIn(reverse('mark_finals_delivered', args=[self.reservation.pk]), self._table())

from datetime import time, timedelta

from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from massageProject.accounts.models import CustomUser
from massageProject.main_app.models import Reservation
from massageProject.main_app.tests.reservations.helpers import ReservationAuditFixTestBase


class AdminSaveWithoutValidationTest(ReservationAuditFixTestBase, TestCase):
    """The superuser-only "save without validation" button on the Reservation
    admin form bypasses Reservation.clean(); every other path still validates."""

    def setUp(self):
        self._make_base_objects()
        self.superuser = CustomUser.objects.create_superuser(
            phone_number='0877777777', email='admin@example.com', password='password123',
        )
        self.staff = CustomUser.objects.create_user(
            phone_number='0899999999', email='staff@example.com', password='password123', is_staff=True,
        )
        self.staff.user_permissions.add(*self._reservation_permissions())
        self.add_url = reverse('admin:main_app_reservation_add')

    def _reservation_permissions(self):
        return Permission.objects.filter(
            content_type__app_label='main_app', codename__endswith='_reservation',
        )

    def _post_data(self, **extra):
        # Today, one hour from now — inside the 2-hour lead time, so clean() rejects it.
        soon = timezone.localtime() + timedelta(hours=1)
        data = {
            'date': soon.date().isoformat(),
            'time': soon.strftime('%H:%M'),
            'user': self.user.pk,
            'status': Reservation.STATUS_ACTIVE,
            'service': self.service.pk,
            'specialist': self.specialist.pk,
            'additional_text': '',
        }
        data.update(extra)
        return data

    def test_superuser_button_saves_invalid_reservation(self):
        self.client.force_login(self.superuser)
        response = self.client.post(self.add_url, self._post_data(_save_without_validation='1'))

        self.assertRedirects(response, reverse('admin:main_app_reservation_changelist'))
        self.assertEqual(Reservation.all_objects.count(), 1)
        entry = LogEntry.objects.get()
        self.assertIn('без валидация', entry.get_change_message())

    def test_non_superuser_button_still_validates(self):
        self.client.force_login(self.staff)
        response = self.client.post(self.add_url, self._post_data(_save_without_validation='1'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['adminform'].form.errors)
        self.assertEqual(Reservation.all_objects.count(), 0)

    def test_normal_save_still_validates(self):
        self.client.force_login(self.superuser)
        response = self.client.post(self.add_url, self._post_data(_save='1'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['adminform'].form.errors)
        self.assertEqual(Reservation.all_objects.count(), 0)

    def test_status_change_without_validation_stamps_audit_fields(self):
        booking_date = (timezone.now() + timedelta(days=3)).date()
        reservation = Reservation.objects.create(
            service=self.service, specialist=self.specialist, user=self.user,
            date=booking_date, time=time(10, 0),
        )
        # Move it into the past directly so any validated save would now fail.
        Reservation.all_objects.filter(pk=reservation.pk).update(date=booking_date - timedelta(days=10))

        self.client.force_login(self.superuser)
        url = reverse('admin:main_app_reservation_change', args=[reservation.pk])
        response = self.client.post(url, self._post_data(
            date=(booking_date - timedelta(days=10)).isoformat(), time='10:00',
            status=Reservation.STATUS_COMPLETED, _save_without_validation='1',
        ))

        self.assertRedirects(response, reverse('admin:main_app_reservation_changelist'))
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.STATUS_COMPLETED)
        self.assertEqual(reservation.status_updated_by, self.superuser)
        self.assertIsNotNone(reservation.status_updated_at)

    def test_button_rendered_only_for_superuser(self):
        self.client.force_login(self.superuser)
        self.assertContains(self.client.get(self.add_url), 'name="_save_without_validation"')

        self.client.force_login(self.staff)
        self.assertNotContains(self.client.get(self.add_url), 'name="_save_without_validation"')

from datetime import time, timedelta

from django.contrib import admin
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from massageProject.accounts.admin import AppUserAdmin
from massageProject.accounts.models import CustomUser
from massageProject.main_app.admin import mark_as_completed, mark_as_noshow
from massageProject.main_app.models import Reservation
from massageProject.main_app.tests.reservations.helpers import ReservationAuditFixTestBase


class AdminBulkActionSkipsDeletedTest(ReservationAuditFixTestBase, TestCase):
    """1.2 — bulk admin actions must not resurrect soft-deleted reservations."""

    def setUp(self):
        self._make_base_objects()
        booking_date = (timezone.now() + timedelta(days=3)).date()
        self.active_res = Reservation.objects.create(
            service=self.service, specialist=self.specialist, user=self.user,
            date=booking_date, time=time(10, 0),
        )
        self.deleted_res = Reservation.objects.create(
            service=self.service, specialist=self.specialist, user=self.user,
            date=booking_date, time=time(11, 0),
        )
        self.deleted_res.change_status(Reservation.STATUS_DELETED, user=self.user)

    def test_mark_as_completed_skips_deleted(self):
        queryset = Reservation.all_objects.filter(pk__in=[self.active_res.pk, self.deleted_res.pk])
        mark_as_completed(modeladmin=_FakeModelAdmin(), request=_FakeRequest(self.user), queryset=queryset)

        self.active_res.refresh_from_db()
        self.deleted_res.refresh_from_db()
        self.assertEqual(self.active_res.status, Reservation.STATUS_COMPLETED)
        self.assertEqual(self.deleted_res.status, Reservation.STATUS_DELETED)

    def test_mark_as_noshow_skips_deleted(self):
        queryset = Reservation.all_objects.filter(pk__in=[self.active_res.pk, self.deleted_res.pk])
        mark_as_noshow(modeladmin=_FakeModelAdmin(), request=_FakeRequest(self.user), queryset=queryset)

        self.active_res.refresh_from_db()
        self.deleted_res.refresh_from_db()
        self.assertEqual(self.active_res.status, Reservation.STATUS_NOSHOW)
        self.assertEqual(self.deleted_res.status, Reservation.STATUS_DELETED)


class _FakeRequest:
    def __init__(self, user):
        self.user = user


class _FakeModelAdmin:
    def message_user(self, request, message, level=None):
        pass


class AdminReservationsCountAnnotationTest(ReservationAuditFixTestBase, TestCase):
    """3.2 — reservations_count must use the annotated value (no per-row
    query) and must not count soft-deleted reservations."""

    def setUp(self):
        self._make_base_objects()

    def test_reservations_count_excludes_deleted_via_annotation(self):
        booking_date = (timezone.now() + timedelta(days=3)).date()
        Reservation.objects.create(
            service=self.service, specialist=self.specialist, user=self.user,
            date=booking_date, time=time(10, 0),
        )
        to_delete = Reservation.objects.create(
            service=self.service, specialist=self.specialist, user=self.user,
            date=booking_date, time=time(11, 0),
        )
        to_delete.change_status(Reservation.STATUS_DELETED, user=self.user)

        admin_instance = AppUserAdmin(CustomUser, admin.site)
        queryset = admin_instance.get_queryset(_FakeRequest(self.user))
        obj = queryset.get(pk=self.user.pk)

        self.assertEqual(obj._reservations_count, 1)
        self.assertIn('1', admin_instance.reservations_count(obj))


class AdminStatusChangeStampingTest(ReservationAuditFixTestBase, TestCase):
    """3.4 — status changes via the admin changeform must go through
    change_status() so audit stamping isn't duplicated/drifted."""

    def setUp(self):
        self._make_base_objects()
        self.admin_user = CustomUser.objects.create_superuser(
            email='admin-audit@example.com', phone_number='0888888898', password='testpass123',
        )
        self.client = Client()
        self.client.force_login(self.admin_user)
        booking_date = (timezone.now() + timedelta(days=3)).date()
        self.reservation = Reservation.objects.create(
            service=self.service, specialist=self.specialist, user=self.user,
            date=booking_date, time=time(10, 0),
        )

    def test_changing_status_via_admin_stamps_audit_fields(self):
        url = reverse('admin:main_app_reservation_change', args=[self.reservation.pk])
        response = self.client.post(url, {
            'date': self.reservation.date, 'time': self.reservation.time,
            'user': self.user.pk, 'status': Reservation.STATUS_COMPLETED,
            'service': self.service.pk, 'specialist': self.specialist.pk,
            'additional_text': '',
        })
        self.assertIn(response.status_code, (200, 302))

        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, Reservation.STATUS_COMPLETED)
        self.assertIsNotNone(self.reservation.status_updated_at)
        self.assertEqual(self.reservation.status_updated_by, self.admin_user)

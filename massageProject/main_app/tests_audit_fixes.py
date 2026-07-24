import threading
from datetime import time, timedelta
from unittest.mock import patch

from django import db
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.db import IntegrityError
from django.test import Client, RequestFactory, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from massageProject.accounts.admin import AppUserAdmin
from massageProject.accounts.forms import SocialCompleteProfileForm
from massageProject.accounts.models import CustomUser
from massageProject.accounts.tests_google_oauth import make_sociallogin
from massageProject.main_app.admin import mark_as_completed, mark_as_noshow
from massageProject.main_app.models import Reservation, Service, Specialist, WorkingHours


class ReservationAuditFixTestBase:
    def _make_base_objects(self):
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


class DoubleBookingRaceConditionTest(ReservationAuditFixTestBase, TransactionTestCase):
    """1.1 — concurrent bookings for the identical slot must not both succeed."""

    def setUp(self):
        self._make_base_objects()

    def test_concurrent_identical_slot_bookings_only_one_succeeds(self):
        booking_date = (timezone.now() + timedelta(days=3)).date()
        results = []

        def book():
            try:
                Reservation.objects.create(
                    service=self.service,
                    specialist=self.specialist,
                    user=self.user,
                    date=booking_date,
                    time=time(10, 0),
                )
                results.append('ok')
            except Exception as exc:
                results.append(type(exc).__name__)
            finally:
                db.connections.close_all()

        t1 = threading.Thread(target=book)
        t2 = threading.Thread(target=book)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.assertEqual(results.count('ok'), 1, f"expected exactly one booking to succeed, got: {results}")
        self.assertEqual(
            Reservation.objects.filter(date=booking_date, time=time(10, 0), status=Reservation.STATUS_ACTIVE).count(),
            1,
        )


class UniqueActiveSlotConstraintTest(ReservationAuditFixTestBase, TestCase):
    """Defense-in-depth DB constraint from 1.1."""

    def setUp(self):
        self._make_base_objects()

    def test_db_constraint_blocks_duplicate_active_slot_bypassing_clean(self):
        booking_date = (timezone.now() + timedelta(days=3)).date()
        Reservation.objects.create(
            service=self.service, specialist=self.specialist, user=self.user,
            date=booking_date, time=time(10, 0),
        )
        dup = Reservation(
            service=self.service, specialist=self.specialist, user=self.user,
            date=booking_date, time=time(10, 0),
        )
        with self.assertRaises(IntegrityError):
            Reservation.objects.bulk_create([dup])


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


class MidnightWraparoundTest(ReservationAuditFixTestBase, TestCase):
    """1.3 — a booking whose end crosses midnight must be rejected, not wrapped."""

    def setUp(self):
        self._make_base_objects()

    def test_booking_that_would_end_past_midnight_is_rejected(self):
        booking_date = (timezone.now() + timedelta(days=3)).date()
        WorkingHours.objects.update_or_create(
            specialist=self.specialist,
            day_of_week=booking_date.weekday(),
            defaults={'start_time': time(9, 0), 'end_time': time(23, 30)},
        )

        reservation = Reservation(
            service=self.service,  # 60-minute service
            specialist=self.specialist,
            user=self.user,
            date=booking_date,
            time=time(23, 0),  # would end at next-day 00:00
        )
        with self.assertRaises(ValidationError):
            reservation.save()


class NearTermActiveEditTest(ReservationAuditFixTestBase, TestCase):
    """1.4 — editing an unrelated field on an already-active, near-term
    reservation must not be blocked by the lead-time check."""

    def setUp(self):
        self._make_base_objects()

    def test_editing_additional_text_on_near_term_reservation_succeeds(self):
        target_dt = timezone.localtime(timezone.now()) + timedelta(minutes=90)
        WorkingHours.objects.update_or_create(
            specialist=self.specialist,
            day_of_week=target_dt.date().weekday(),
            defaults={'start_time': time(0, 0), 'end_time': time(23, 59)},
        )
        # bulk_create bypasses save()/full_clean() so we can seed an
        # already-active, already near-term reservation directly.
        Reservation.objects.bulk_create([Reservation(
            service=self.service, specialist=self.specialist, user=self.user,
            date=target_dt.date(), time=target_dt.time().replace(microsecond=0),
        )])

        reservation = Reservation.objects.get(
            date=target_dt.date(), time=target_dt.time().replace(microsecond=0),
        )
        reservation.additional_text = 'updated note'
        reservation.save()  # must not raise ValidationError

        reservation.refresh_from_db()
        self.assertEqual(reservation.additional_text, 'updated note')

    def test_rescheduling_a_near_term_reservation_still_enforces_lead_time(self):
        target_dt = timezone.localtime(timezone.now()) + timedelta(minutes=90)
        WorkingHours.objects.update_or_create(
            specialist=self.specialist,
            day_of_week=target_dt.date().weekday(),
            defaults={'start_time': time(0, 0), 'end_time': time(23, 59)},
        )
        Reservation.objects.bulk_create([Reservation(
            service=self.service, specialist=self.specialist, user=self.user,
            date=target_dt.date(), time=target_dt.time().replace(microsecond=0),
        )])
        reservation = Reservation.objects.get(
            date=target_dt.date(), time=target_dt.time().replace(microsecond=0),
        )
        # Rescheduling to another near-term slot must still hit the lead-time check.
        reservation.time = (target_dt + timedelta(minutes=5)).time().replace(microsecond=0)
        with self.assertRaises(ValidationError):
            reservation.save()


TURNSTILE_PATCH = 'massageProject.accounts.booking_auth_views.verify_turnstile_token'


class RegistrationEmailRaceTest(TestCase):
    """1.5 — a concurrent email collision at save-time must return a graceful
    error instead of an unhandled IntegrityError/500."""

    def setUp(self):
        cache.clear()
        self.client = Client()

    def _session_with_verified_email(self, email):
        from massageProject.accounts.booking_auth_views import SIGNUP_EMAIL_SESSION_KEY
        session = self.client.session
        session[SIGNUP_EMAIL_SESSION_KEY] = email
        session[SIGNUP_EMAIL_SESSION_KEY + '_expires'] = (
            timezone.now() + timezone.timedelta(minutes=15)
        ).isoformat()
        session.save()

    @patch(TURNSTILE_PATCH, return_value=True)
    def test_email_taken_between_verification_and_save_returns_409_not_500(self, mock_turnstile):
        CustomUser.objects.create_user(
            phone_number='0888920001', email='raced@example.com', password='Whatever!123',
        )
        self._session_with_verified_email('raced@example.com')

        response = self.client.post(reverse('auth_register'), {
            'first_name': 'Petar', 'last_name': 'Georgiev',
            'phone_number': '0888920002', 'password': 'ComplexPass!123',
            'turnstile_token': 'ok',
        })

        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.json()['success'])
        self.assertEqual(CustomUser.objects.filter(phone_number='0888920002').count(), 0)


class SocialClaimConcurrencyGuardTest(TestCase):
    """1.6 — a phone number claimed concurrently (password set in between
    validation and save) must fail loudly, not silently overwrite."""

    def test_save_rechecks_password_after_locking_and_raises_instead_of_overwriting(self):
        User = get_user_model()
        staff_created = User.objects.create_user(
            email='placeholder@example.com', phone_number='0899555001', password=None,
        )
        sociallogin = make_sociallogin('newcomer@example.com')
        form = SocialCompleteProfileForm(data={
            'email': 'newcomer@example.com', 'first_name': 'Ivan',
            'last_name': 'Petrov', 'phone_number': '0899555001',
        }, sociallogin=sociallogin)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form._claimed_user, staff_created)

        # Simulate a concurrent request setting a password on this same
        # passwordless user after our clean() ran but before our save().
        staff_created.set_password('someone-else-claimed-this')
        staff_created.save()

        request = RequestFactory().post('/accounts/social/signup/')
        with self.assertRaises(ValidationError):
            form.save(request)

        staff_created.refresh_from_db()
        self.assertEqual(staff_created.email, 'placeholder@example.com')
        self.assertEqual(staff_created.first_name, '')


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

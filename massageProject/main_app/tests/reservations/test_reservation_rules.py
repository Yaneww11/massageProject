from datetime import time, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from massageProject.main_app.models import Reservation, WorkingHours
from massageProject.main_app.tests.reservations.helpers import ReservationAuditFixTestBase


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

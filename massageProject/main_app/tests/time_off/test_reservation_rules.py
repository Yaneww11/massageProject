from datetime import time

from django.core.exceptions import ValidationError

from massageProject.main_app.models import Reservation, Specialist, WorkingHours
from massageProject.main_app.tests.time_off.helpers import TimeOffTestBase, aware


class ReservationBlockedByTimeOffTest(TimeOffTestBase):
    """Time Off 12:00-14:00; the service lasts 60 minutes."""

    def setUp(self):
        super().setUp()
        self.make_time_off(aware(self.day, 12), aware(self.day, 14))

    def _book(self, hour, minute=0, specialist=None):
        return Reservation.objects.create(
            user=self.user, service=self.service, specialist=specialist or self.specialist,
            date=self.day, time=time(hour, minute),
        )

    def test_booking_inside_time_off_refused(self):
        with self.assertRaises(ValidationError):
            self._book(12, 30)

    def test_booking_partially_overlapping_start_refused(self):
        with self.assertRaises(ValidationError):
            self._book(11, 30)

    def test_booking_partially_overlapping_end_refused(self):
        with self.assertRaises(ValidationError):
            self._book(13, 30)

    def test_booking_ending_at_time_off_start_allowed(self):
        self._book(11)
        self.assertEqual(Reservation.objects.count(), 1)

    def test_booking_starting_at_time_off_end_allowed(self):
        self._book(14)
        self.assertEqual(Reservation.objects.count(), 1)

    def test_reschedule_into_time_off_refused(self):
        reservation = self._book(10)
        reservation.time = time(12, 0)
        with self.assertRaises(ValidationError):
            reservation.save()

    def test_unrelated_field_edit_not_blocked(self):
        reservation = self._book(15)
        # Time Off that would now cover this reservation, written past clean()
        # the way an admin bulk edit could leave the data.
        from massageProject.main_app.models import TimeOff
        TimeOff.objects.update(end=aware(self.day, 17))
        reservation.refresh_from_db()
        reservation.additional_text = 'please bring a towel'
        reservation.save()

    def test_other_specialists_time_off_ignored(self):
        other = Specialist.objects.create(name='Other', description='d', phone_number='0888000111', email='o@e.com')
        WorkingHours.objects.create(specialist=other, day_of_week=self.day.weekday(), start_time=time(9), end_time=time(17))
        self._book(12, specialist=other)
        self.assertEqual(Reservation.objects.count(), 1)

    def test_error_message_names_the_specialist(self):
        with self.assertRaises(ValidationError) as ctx:
            self._book(12)
        self.assertIn(self.specialist.name, ' '.join(ctx.exception.messages))

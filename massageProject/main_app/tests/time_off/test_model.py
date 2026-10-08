from datetime import time, timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone

from massageProject.main_app.models import Reservation, TimeOff
from massageProject.main_app.tests.time_off.helpers import TimeOffTestBase, aware


class TimeOffValidationTest(TimeOffTestBase):

    def test_valid_time_off_is_saved(self):
        self.make_time_off(aware(self.day, 10), aware(self.day, 12), note='doctor')
        self.assertEqual(TimeOff.objects.count(), 1)

    def test_end_equal_to_start_refused(self):
        with self.assertRaises(ValidationError):
            self.make_time_off(aware(self.day, 10), aware(self.day, 10))

    def test_end_before_start_refused(self):
        with self.assertRaises(ValidationError):
            self.make_time_off(aware(self.day, 12), aware(self.day, 10))

    def test_start_not_on_half_hour_refused(self):
        with self.assertRaises(ValidationError):
            self.make_time_off(aware(self.day, 10, 15), aware(self.day, 12))

    def test_end_not_on_half_hour_refused(self):
        with self.assertRaises(ValidationError):
            self.make_time_off(aware(self.day, 10), aware(self.day, 12, 45))

    def test_seconds_refused(self):
        with self.assertRaises(ValidationError):
            self.make_time_off(aware(self.day, 10) + timedelta(seconds=5), aware(self.day, 12))

    def test_end_in_past_refused(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        with self.assertRaises(ValidationError):
            self.make_time_off(aware(yesterday, 10), aware(yesterday, 12))

    def test_start_in_past_but_end_in_future_allowed(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        self.make_time_off(aware(yesterday, 0), aware(self.day, 0))
        self.assertEqual(TimeOff.objects.count(), 1)

    def test_overlapping_time_off_allowed(self):
        self.make_time_off(aware(self.day, 10), aware(self.day, 12))
        self.make_time_off(aware(self.day, 11), aware(self.day, 13))
        self.assertEqual(TimeOff.objects.count(), 2)

    def test_existing_entry_with_end_now_in_past_can_be_resaved(self):
        time_off = self.make_time_off(aware(self.day, 10), aware(self.day, 12))
        yesterday = timezone.localdate() - timedelta(days=1)
        TimeOff.objects.filter(pk=time_off.pk).update(start=aware(yesterday, 10), end=aware(yesterday, 12))
        time_off.refresh_from_db()
        time_off.note = 'edited in admin'
        time_off.save()


class TimeOffReservationClashTest(TimeOffTestBase):

    def _book(self, hour, status=Reservation.STATUS_ACTIVE, specialist=None):
        reservation = Reservation.objects.create(
            user=self.user, service=self.service, specialist=specialist or self.specialist,
            date=self.day, time=time(hour, 0),
        )
        if status != Reservation.STATUS_ACTIVE:
            reservation.change_status(status)
        return reservation

    def test_clash_with_active_reservation_refused_and_listed(self):
        self._book(10)
        self._book(14)
        with self.assertRaises(ValidationError) as ctx:
            self.make_time_off(aware(self.day, 9), aware(self.day, 17))
        message = ' '.join(ctx.exception.messages)
        self.assertIn(self.day.strftime('%d.%m.%Y'), message)
        self.assertIn('10:00', message)
        self.assertIn('14:00', message)
        self.assertIn(self.service.name, message)
        self.assertEqual(TimeOff.objects.count(), 0)

    def test_partial_overlap_refused(self):
        self._book(10)  # 10:00-11:00
        with self.assertRaises(ValidationError):
            self.make_time_off(aware(self.day, 10, 30), aware(self.day, 12))

    def test_touching_reservation_edge_allowed(self):
        self._book(10)  # 10:00-11:00
        self.make_time_off(aware(self.day, 11), aware(self.day, 12))
        self.make_time_off(aware(self.day, 9), aware(self.day, 10))
        self.assertEqual(TimeOff.objects.count(), 2)

    def test_clash_with_cancelled_reservation_allowed(self):
        self._book(10, status=Reservation.STATUS_DELETED)
        self.make_time_off(aware(self.day, 9), aware(self.day, 17))
        self.assertEqual(TimeOff.objects.count(), 1)

    def test_clash_with_completed_reservation_allowed(self):
        self._book(10, status=Reservation.STATUS_COMPLETED)
        self.make_time_off(aware(self.day, 9), aware(self.day, 17))
        self.assertEqual(TimeOff.objects.count(), 1)

    def test_multi_day_time_off_detects_clash_on_later_day(self):
        later = self.day + timedelta(days=2)
        Reservation.objects.create(
            user=self.user, service=self.service, specialist=self.specialist, date=later, time=time(15, 0),
        )
        with self.assertRaises(ValidationError):
            self.make_time_off(aware(self.day, 0), aware(later + timedelta(days=1), 0))

    def test_other_specialists_reservation_ignored(self):
        from massageProject.main_app.models import Specialist, WorkingHours
        other = Specialist.objects.create(name='Other', description='d', phone_number='0888000111', email='o@e.com')
        WorkingHours.objects.create(specialist=other, day_of_week=self.day.weekday(), start_time=time(9), end_time=time(17))
        self._book(10, specialist=other)
        self.make_time_off(aware(self.day, 9), aware(self.day, 17))
        self.assertEqual(TimeOff.objects.count(), 1)


class TimeOffPeriodDisplayTest(TimeOffTestBase):

    def test_single_whole_day(self):
        entry = self.make_time_off(aware(self.day, 0), aware(self.day + timedelta(days=1), 0))
        self.assertEqual(entry.period_display, f"{self.day:%d.%m.%Y}")

    def test_several_whole_days(self):
        last = self.day + timedelta(days=4)
        entry = self.make_time_off(aware(self.day, 0), aware(last + timedelta(days=1), 0))
        self.assertEqual(entry.period_display, f"{self.day:%d.%m.%Y} - {last:%d.%m.%Y}")

    def test_hours_within_one_day(self):
        entry = self.make_time_off(aware(self.day, 12), aware(self.day, 14, 30))
        self.assertEqual(entry.period_display, f"{self.day:%d.%m.%Y}, 12:00 - 14:30")

    def test_hours_across_days(self):
        nxt = self.day + timedelta(days=1)
        entry = self.make_time_off(aware(self.day, 12), aware(nxt, 10))
        self.assertEqual(entry.period_display, f"{self.day:%d.%m.%Y} 12:00 - {nxt:%d.%m.%Y} 10:00")

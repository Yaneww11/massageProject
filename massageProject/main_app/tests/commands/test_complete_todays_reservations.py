from datetime import date, datetime, time
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.utils import timezone

from massageProject.main_app.models import Reservation
from massageProject.main_app.tests.helpers import BugFixTestBase

TODAY = date(2026, 10, 9)
EVENING = timezone.make_aware(datetime(2026, 10, 9, 20, 0))


@patch('massageProject.main_app.management.commands.complete_todays_reservations.timezone.localtime',
       return_value=EVENING)
class CompleteTodaysReservationsTest(BugFixTestBase):
    def _reservation(self, day, at, status=Reservation.STATUS_ACTIVE):
        r = Reservation(
            service=self.service, specialist=self.specialist, user=self.user,
            date=day, time=at, status=status,
        )
        r._skip_validation = True  # seed past slots, bypassing the lead-time check
        r.save()
        return r

    def _run(self, *args):
        out = StringIO()
        call_command('complete_todays_reservations', *args, stdout=out)
        return out.getvalue()

    def test_completes_todays_ended_active_reservations(self, _now):
        r = self._reservation(TODAY, time(10, 0))
        self._run()
        r.refresh_from_db()
        self.assertEqual(r.status, Reservation.STATUS_COMPLETED)
        self.assertIsNotNone(r.status_updated_at)

    def test_leaves_other_days_and_other_statuses_alone(self, _now):
        tomorrow = self._reservation(date(2026, 10, 10), time(10, 0))
        yesterday = self._reservation(date(2026, 10, 8), time(10, 0))
        deleted = self._reservation(TODAY, time(11, 0), status=Reservation.STATUS_DELETED)
        no_show = self._reservation(TODAY, time(12, 0), status=Reservation.STATUS_NOSHOW)
        self._run()
        for r, status in [
            (tomorrow, Reservation.STATUS_ACTIVE), (yesterday, Reservation.STATUS_ACTIVE),
            (deleted, Reservation.STATUS_DELETED), (no_show, Reservation.STATUS_NOSHOW),
        ]:
            r.refresh_from_db()
            self.assertEqual(r.status, status)

    def test_skips_reservation_still_in_progress(self, _now):
        r = self._reservation(TODAY, time(19, 30))  # 60 min -> ends 20:30
        self._run()
        r.refresh_from_db()
        self.assertEqual(r.status, Reservation.STATUS_ACTIVE)

    def test_dry_run_changes_nothing(self, _now):
        r = self._reservation(TODAY, time(10, 0))
        output = self._run('--dry-run')
        r.refresh_from_db()
        self.assertEqual(r.status, Reservation.STATUS_ACTIVE)
        self.assertIn('1 reservation(s) to complete', output)

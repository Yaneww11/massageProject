from datetime import datetime, time, timedelta

from django.utils import timezone

from massageProject.main_app.models import TimeOff
from massageProject.main_app.tests.helpers import BugFixTestBase


def aware(day, hour, minute=0):
    return timezone.make_aware(datetime.combine(day, time(hour, minute)))


class TimeOffTestBase(BugFixTestBase):
    """BugFixTestBase gives one specialist working 09:00-17:00 every day and a
    60-minute service. `self.day` is far enough out to clear the 2h lead time."""

    def setUp(self):
        super().setUp()
        self.day = timezone.localdate() + timedelta(days=3)

    def make_time_off(self, start, end, specialist=None, **extra):
        time_off = TimeOff(specialist=specialist or self.specialist, start=start, end=end, **extra)
        time_off.save()
        return time_off

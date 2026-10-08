from datetime import timedelta

from django.urls import reverse

from massageProject.main_app.tests.time_off.helpers import TimeOffTestBase, aware


class AvailabilityWithTimeOffTest(TimeOffTestBase):

    def _slots(self):
        self.login()
        response = self.client.get(
            reverse('check_availability')
            + f'?specialist_id={self.specialist.pk}&date={self.day:%Y-%m-%d}&service_id={self.service.pk}'
        )
        return {s['time']: s for s in response.json()['slots']}

    def test_slots_overlapping_time_off_are_taken(self):
        self.make_time_off(aware(self.day, 12), aware(self.day, 14))
        slots = self._slots()
        for t in ('11:30', '12:00', '12:30', '13:00', '13:30'):
            self.assertFalse(slots[t]['available'], t)
            self.assertEqual(slots[t]['reason'], 'taken', t)
        for t in ('11:00', '14:00'):
            self.assertTrue(slots[t]['available'], t)

    def test_all_day_time_off_leaves_no_available_slots(self):
        self.make_time_off(aware(self.day, 0), aware(self.day + timedelta(days=1), 0))
        slots = self._slots()
        self.assertTrue(slots)
        self.assertFalse(any(s['available'] for s in slots.values()))

    def test_multi_day_time_off_covering_the_date_blocks_it(self):
        self.make_time_off(aware(self.day - timedelta(days=1), 0), aware(self.day + timedelta(days=2), 0))
        self.assertFalse(any(s['available'] for s in self._slots().values()))

    def test_time_off_on_other_day_ignored(self):
        other_day = self.day + timedelta(days=1)
        self.make_time_off(aware(other_day, 0), aware(other_day + timedelta(days=1), 0))
        self.assertTrue(all(s['available'] for s in self._slots().values()))

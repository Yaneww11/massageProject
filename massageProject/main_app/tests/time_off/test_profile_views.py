from datetime import time, timedelta

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from massageProject.accounts.models import CustomUser
from massageProject.main_app.models import Reservation, Service, Specialist, TimeOff, WorkingHours
from massageProject.main_app.tests.time_off.helpers import aware


class TimeOffProfileTestBase(TestCase):
    def setUp(self):
        ct = ContentType.objects.get_for_model(Reservation)
        view_all = Permission.objects.get(content_type=ct, codename='view_all_reservations')
        view_own = Permission.objects.get(content_type=ct, codename='view_specialist_reservations')

        self.service = Service.objects.create(
            name='Massage', description='d', price=50, duration_in_minutes=60, short_description='s',
        )
        self.specialist_user = CustomUser.objects.create_user(phone_number='0888700001', email='0888700001@example.com', password='pass12345')
        self.specialist_user.user_permissions.add(view_own)
        self.specialist = Specialist.objects.create(
            name='Ivan', description='d', phone_number='0888700002', email='ivan@example.com',
            user=self.specialist_user,
        )
        self.other_user = CustomUser.objects.create_user(phone_number='0888700003', email='0888700003@example.com', password='pass12345')
        self.other_user.user_permissions.add(view_own)
        self.other_specialist = Specialist.objects.create(
            name='Zora', description='d', phone_number='0888700004', email='zora@example.com',
            user=self.other_user,
        )
        self.staff_user = CustomUser.objects.create_user(phone_number='0888700005', email='0888700005@example.com', password='pass12345')
        self.staff_user.user_permissions.add(view_all)
        self.client_user = CustomUser.objects.create_user(phone_number='0888700006', email='0888700006@example.com', password='pass12345')

        for specialist in (self.specialist, self.other_specialist):
            for day in range(7):
                WorkingHours.objects.create(
                    specialist=specialist, day_of_week=day, start_time=time(9), end_time=time(17),
                )

        self.day = timezone.localdate() + timedelta(days=3)
        self.client = Client()

    def _post_data(self, **overrides):
        data = {
            'start_date': self.day.isoformat(),
            'end_date': self.day.isoformat(),
            'start_time': '12:00',
            'end_time': '14:00',
            'note': 'doctor',
        }
        data.update(overrides)
        return data

    def _entry(self, specialist, day=None, start_hour=10, end_hour=11):
        day = day or self.day
        return TimeOff.objects.create(specialist=specialist, start=aware(day, start_hour), end=aware(day, end_hour))


class TimeOffSectionVisibilityTest(TimeOffProfileTestBase):

    def test_specialist_sees_only_own_upcoming_entries(self):
        own = self._entry(self.specialist)
        self._entry(self.other_specialist)
        self.client.force_login(self.specialist_user)
        response = self.client.get(reverse('profile_page'))
        self.assertContains(response, 'time-off-section')
        self.assertEqual(list(response.context['time_off_entries']), [own])

    def test_staff_sees_all_specialists_entries(self):
        a = self._entry(self.specialist)
        b = self._entry(self.other_specialist, start_hour=12, end_hour=13)
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('profile_page'))
        self.assertEqual(list(response.context['time_off_entries']), [a, b])
        self.assertIn('specialist', response.context['time_off_form'].fields)

    def test_specialist_form_has_no_specialist_dropdown(self):
        self.client.force_login(self.specialist_user)
        response = self.client.get(reverse('profile_page'))
        self.assertNotIn('specialist', response.context['time_off_form'].fields)

    def test_past_entries_not_listed_but_ongoing_are(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        past = self._entry(self.specialist)
        TimeOff.objects.filter(pk=past.pk).update(start=aware(yesterday, 10), end=aware(yesterday, 11))
        ongoing = self._entry(self.specialist)
        TimeOff.objects.filter(pk=ongoing.pk).update(start=aware(yesterday, 10))
        self.client.force_login(self.specialist_user)
        response = self.client.get(reverse('profile_page'))
        self.assertEqual([e.pk for e in response.context['time_off_entries']], [ongoing.pk])

    def test_section_absent_for_clients(self):
        self.client.force_login(self.client_user)
        response = self.client.get(reverse('profile_page'))
        self.assertNotContains(response, 'time-off-section')
        self.assertNotIn('time_off_entries', response.context)


class TimeOffCreateTest(TimeOffProfileTestBase):

    @property
    def url(self):
        return reverse('time_off_create')

    def test_specialist_creates_own_entry(self):
        self.client.force_login(self.specialist_user)
        response = self.client.post(self.url, self._post_data())
        self.assertRedirects(response, reverse('profile_page'), fetch_redirect_response=False)
        entry = TimeOff.objects.get()
        self.assertEqual(entry.specialist, self.specialist)
        self.assertEqual(entry.start, aware(self.day, 12))
        self.assertEqual(entry.end, aware(self.day, 14))
        self.assertEqual(entry.note, 'doctor')
        self.assertEqual(entry.created_by, self.specialist_user)

    def test_specialist_cannot_target_another_specialist(self):
        self.client.force_login(self.specialist_user)
        self.client.post(self.url, self._post_data(specialist=self.other_specialist.pk))
        self.assertEqual(TimeOff.objects.get().specialist, self.specialist)

    def test_staff_creates_for_any_specialist(self):
        self.client.force_login(self.staff_user)
        self.client.post(self.url, self._post_data(specialist=self.other_specialist.pk))
        self.assertEqual(TimeOff.objects.get().specialist, self.other_specialist)

    def test_staff_must_choose_specialist(self):
        self.client.force_login(self.staff_user)
        response = self.client.post(self.url, self._post_data())
        self.assertEqual(response.status_code, 200)
        self.assertFalse(TimeOff.objects.exists())

    def test_all_day_covers_full_calendar_days(self):
        self.client.force_login(self.specialist_user)
        end_day = self.day + timedelta(days=4)
        self.client.post(self.url, self._post_data(
            all_day='on', end_date=end_day.isoformat(), start_time='', end_time='',
        ))
        entry = TimeOff.objects.get()
        self.assertEqual(entry.start, aware(self.day, 0))
        self.assertEqual(entry.end, aware(end_day + timedelta(days=1), 0))

    def test_times_required_when_not_all_day(self):
        self.client.force_login(self.specialist_user)
        response = self.client.post(self.url, self._post_data(start_time='', end_time=''))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(TimeOff.objects.exists())

    def test_clash_rerenders_profile_with_errors_and_open_modal(self):
        Reservation.objects.create(
            user=self.client_user, service=self.service, specialist=self.specialist,
            date=self.day, time=time(12, 30),
        )
        self.client.force_login(self.specialist_user)
        response = self.client.post(self.url, self._post_data())
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pages/my_profile.html')
        form = response.context['time_off_form']
        self.assertTrue(form.non_field_errors())
        self.assertContains(response, '12:30')
        self.assertContains(response, 'data-open-on-load')
        self.assertFalse(TimeOff.objects.exists())

    def test_client_refused(self):
        self.client.force_login(self.client_user)
        response = self.client.post(self.url, self._post_data())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(TimeOff.objects.exists())

    def test_anonymous_redirected_to_login(self):
        response = self.client.post(self.url, self._post_data())
        self.assertEqual(response.status_code, 302)
        self.assertFalse(TimeOff.objects.exists())

    def test_get_not_allowed(self):
        self.client.force_login(self.specialist_user)
        self.assertEqual(self.client.get(self.url).status_code, 405)


class TimeOffDeleteTest(TimeOffProfileTestBase):

    def _url(self, entry):
        return reverse('time_off_delete', args=[entry.pk])

    def test_specialist_deletes_own_entry(self):
        entry = self._entry(self.specialist)
        self.client.force_login(self.specialist_user)
        response = self.client.post(self._url(entry))
        self.assertRedirects(response, reverse('profile_page'), fetch_redirect_response=False)
        self.assertFalse(TimeOff.objects.exists())

    def test_specialist_cannot_delete_another_specialists_entry(self):
        entry = self._entry(self.other_specialist)
        self.client.force_login(self.specialist_user)
        self.assertEqual(self.client.post(self._url(entry)).status_code, 404)
        self.assertTrue(TimeOff.objects.exists())

    def test_staff_deletes_any_entry(self):
        entry = self._entry(self.other_specialist)
        self.client.force_login(self.staff_user)
        self.client.post(self._url(entry))
        self.assertFalse(TimeOff.objects.exists())

    def test_client_refused(self):
        entry = self._entry(self.specialist)
        self.client.force_login(self.client_user)
        self.assertEqual(self.client.post(self._url(entry)).status_code, 403)
        self.assertTrue(TimeOff.objects.exists())

    def test_anonymous_redirected(self):
        entry = self._entry(self.specialist)
        self.assertEqual(self.client.post(self._url(entry)).status_code, 302)
        self.assertTrue(TimeOff.objects.exists())

    def test_get_not_allowed(self):
        entry = self._entry(self.specialist)
        self.client.force_login(self.specialist_user)
        self.assertEqual(self.client.get(self._url(entry)).status_code, 405)
        self.assertTrue(TimeOff.objects.exists())

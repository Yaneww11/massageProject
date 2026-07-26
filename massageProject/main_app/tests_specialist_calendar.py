from django.test import TestCase
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib import admin as django_admin

from massageProject.main_app.models import Specialist, Reservation
from massageProject.main_app.admin import SpecialistAdmin


class SpecialistUserLinkAndPermissionsTest(TestCase):
    def test_specialist_has_nullable_user_field(self):
        field = Specialist._meta.get_field('user')
        self.assertEqual(field.related_model.__name__, 'CustomUser')
        self.assertTrue(field.null)

    def test_reservation_permissions_exist(self):
        ct = ContentType.objects.get_for_model(Reservation)
        codenames = set(
            Permission.objects.filter(content_type=ct).values_list('codename', flat=True)
        )
        self.assertIn('view_all_reservations', codenames)
        self.assertIn('view_specialist_reservations', codenames)


class SpecialistAdminUserLinkTest(TestCase):
    def test_specialist_admin_exposes_user_field(self):
        admin_instance = SpecialistAdmin(Specialist, django_admin.site)
        self.assertIn('user', admin_instance.list_display)
        self.assertIn('user', admin_instance.autocomplete_fields)


from datetime import time as time_cls, timedelta
from django.utils import timezone

from massageProject.main_app.models import Service, WorkingHours
from massageProject.accounts.models import CustomUser
from massageProject.main_app.views import _build_week_calendar


class BuildWeekCalendarTest(TestCase):
    def setUp(self):
        self.specialist = Specialist.objects.create(
            name='Maria', description='desc', phone_number='0888000000', email='maria@example.com',
        )
        self.service = Service.objects.create(
            name='Massage', description='d', price=50, duration_in_minutes=60, short_description='s',
        )
        self.client_user = CustomUser.objects.create_user(
            phone_number='0888000001', email='client@example.com', password='pass12345',
        )
        candidate = timezone.localdate() + timedelta(days=7)
        while candidate.weekday() != 0:
            candidate += timedelta(days=1)
        self.monday = candidate

    def test_day_without_working_hours_has_none_and_no_reservations(self):
        WorkingHours.objects.create(
            specialist=self.specialist, day_of_week=0, start_time=time_cls(9, 0), end_time=time_cls(17, 0),
        )
        calendar = _build_week_calendar(self.specialist, self.monday)
        tuesday = calendar['days'][1]
        self.assertIsNone(tuesday['working_hours'])
        self.assertEqual(tuesday['reservations'], [])

    def test_reservation_position_percentages(self):
        WorkingHours.objects.create(
            specialist=self.specialist, day_of_week=0, start_time=time_cls(9, 0), end_time=time_cls(17, 0),
        )
        Reservation.objects.create(
            user=self.client_user, service=self.service, specialist=self.specialist,
            date=self.monday, time=time_cls(10, 0),
        )
        calendar = _build_week_calendar(self.specialist, self.monday)
        entry = calendar['days'][0]['reservations'][0]
        # window is 09:00-17:00 = 480 minutes; booking starts 60min in, lasts 60min
        self.assertAlmostEqual(entry['top_pct'], 12.5)
        self.assertAlmostEqual(entry['height_pct'], 12.5)

    def test_no_working_hours_at_all_uses_default_window(self):
        calendar = _build_week_calendar(self.specialist, self.monday)
        labels = [m['label'] for m in calendar['hour_marks']]
        self.assertEqual(labels[0], '08:00')
        self.assertEqual(labels[-1], '20:00')

    def test_visit_count_counts_completed_reservations_with_this_specialist(self):
        WorkingHours.objects.create(
            specialist=self.specialist, day_of_week=0, start_time=time_cls(9, 0), end_time=time_cls(17, 0),
        )
        past = Reservation.objects.create(
            user=self.client_user, service=self.service, specialist=self.specialist,
            date=self.monday, time=time_cls(9, 0),
        )
        past.change_status(Reservation.STATUS_COMPLETED)
        Reservation.objects.create(
            user=self.client_user, service=self.service, specialist=self.specialist,
            date=self.monday, time=time_cls(11, 0),
        )
        calendar = _build_week_calendar(self.specialist, self.monday)
        entry = calendar['days'][0]['reservations'][0]
        self.assertEqual(entry['visit_count'], 1)

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

    def test_percentages_clamped_when_working_hours_shrink(self):
        # Create initial working hours: 14:00-20:00
        WorkingHours.objects.create(
            specialist=self.specialist, day_of_week=0, start_time=time_cls(14, 0), end_time=time_cls(20, 0),
        )

        # Create a reservation at 19:00 (with 60-min service, ends at 20:00)
        # This is valid within the 14:00-20:00 window
        r = Reservation.objects.create(
            user=self.client_user, service=self.service, specialist=self.specialist,
            date=self.monday, time=time_cls(19, 0),
        )

        # Now shrink the working hours to 14:00-18:00
        wh = WorkingHours.objects.get(specialist=self.specialist, day_of_week=0)
        wh.end_time = time_cls(18, 0)
        wh.save()

        # Build the calendar
        # Window is now 14:00-18:00 (240 minutes)
        # Reservation is 19:00-20:00 (outside the window)
        calendar = _build_week_calendar(self.specialist, self.monday)
        entry = calendar['days'][0]['reservations'][0]

        # Percentages should be clamped to [0, 100]
        self.assertLessEqual(entry['top_pct'], 100.0, f"top_pct {entry['top_pct']} exceeds 100")
        self.assertLessEqual(entry['height_pct'], 100.0, f"height_pct {entry['height_pct']} exceeds 100")


from django.test import Client
from django.urls import reverse


class ProfilePageRoleResolutionTest(TestCase):
    def setUp(self):
        self.client = Client()
        ct = ContentType.objects.get_for_model(Reservation)
        self.view_all_perm = Permission.objects.get(content_type=ct, codename='view_all_reservations')
        self.view_specialist_perm = Permission.objects.get(content_type=ct, codename='view_specialist_reservations')

        self.plain_user = CustomUser.objects.create_user(
            phone_number='0888100001', email='plain@example.com', password='pass12345',
        )
        self.specialist_user = CustomUser.objects.create_user(
            phone_number='0888100002', email='specialist@example.com', password='pass12345',
        )
        self.staff_user = CustomUser.objects.create_user(
            phone_number='0888100003', email='staff@example.com', password='pass12345',
        )
        self.specialist = Specialist.objects.create(
            name='Ivan', description='d', phone_number='0888100004', email='ivan@example.com',
            user=self.specialist_user,
        )

    def test_plain_client_sees_client_role(self):
        self.client.force_login(self.plain_user)
        response = self.client.get(reverse('profile_page'))
        self.assertEqual(response.context['role'], 'client')

    def test_specialist_link_without_permission_falls_back_to_client(self):
        self.client.force_login(self.specialist_user)
        response = self.client.get(reverse('profile_page'))
        self.assertEqual(response.context['role'], 'client')

    def test_permission_without_specialist_link_falls_back_to_client(self):
        self.plain_user.user_permissions.add(self.view_specialist_perm)
        self.client.force_login(self.plain_user)
        response = self.client.get(reverse('profile_page'))
        self.assertEqual(response.context['role'], 'client')

    def test_specialist_with_link_and_permission_sees_specialist_role(self):
        self.specialist_user.user_permissions.add(self.view_specialist_perm)
        self.client.force_login(self.specialist_user)
        response = self.client.get(reverse('profile_page'))
        self.assertEqual(response.context['role'], 'specialist')
        self.assertEqual(response.context['calendar_specialist'], self.specialist)

    def test_staff_with_view_all_reservations_sees_staff_role(self):
        self.staff_user.user_permissions.add(self.view_all_perm)
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('profile_page'))
        self.assertEqual(response.context['role'], 'staff')
        self.assertIn(self.specialist, response.context['specialists'])

    def test_staff_takes_precedence_over_specialist_when_both_apply(self):
        self.specialist_user.user_permissions.add(self.view_specialist_perm, self.view_all_perm)
        self.client.force_login(self.specialist_user)
        response = self.client.get(reverse('profile_page'))
        self.assertEqual(response.context['role'], 'staff')

    def test_staff_can_select_specialist_via_get_param(self):
        other_specialist = Specialist.objects.create(
            name='Zora', description='d', phone_number='0888100006', email='zora@example.com',
        )
        self.staff_user.user_permissions.add(self.view_all_perm)
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('profile_page'), {'specialist_id': other_specialist.pk})
        self.assertEqual(response.context['calendar_specialist'], other_specialist)


class ProfilePageTemplateRenderingTest(TestCase):
    def setUp(self):
        self.client = Client()
        ct = ContentType.objects.get_for_model(Reservation)
        view_all_perm = Permission.objects.get(content_type=ct, codename='view_all_reservations')
        view_specialist_perm = Permission.objects.get(content_type=ct, codename='view_specialist_reservations')

        self.plain_user = CustomUser.objects.create_user(
            phone_number='0888200001', email='plain2@example.com', password='pass12345',
        )
        self.specialist_user = CustomUser.objects.create_user(
            phone_number='0888200002', email='specialist2@example.com', password='pass12345',
        )
        self.staff_user = CustomUser.objects.create_user(
            phone_number='0888200003', email='staff2@example.com', password='pass12345',
        )
        Specialist.objects.create(
            name='Petya', description='d', phone_number='0888200004', email='petya@example.com',
            user=self.specialist_user,
        )
        self.specialist_user.user_permissions.add(view_specialist_perm)
        self.staff_user.user_permissions.add(view_all_perm)

    def test_client_role_renders_existing_sections_not_calendar(self):
        self.client.force_login(self.plain_user)
        response = self.client.get(reverse('profile_page'))
        self.assertContains(response, 'proof-teaser-card')
        self.assertNotContains(response, 'specialist-calendar')

    def test_specialist_role_renders_calendar_not_client_sections(self):
        self.client.force_login(self.specialist_user)
        response = self.client.get(reverse('profile_page'))
        self.assertContains(response, 'specialist-calendar')
        self.assertNotContains(response, 'proof-teaser-card')

    def test_staff_role_renders_specialist_picker(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('profile_page'))
        self.assertContains(response, 'specialist-picker-form')

    def test_today_stats_independent_of_browsed_week(self):
        specialist = Specialist.objects.get(user=self.specialist_user)
        service = Service.objects.create(
            name='Massage', description='d', price=50, duration_in_minutes=60, short_description='s',
        )
        client_user = CustomUser.objects.create_user(
            phone_number='0888200005', email='client2@example.com', password='pass12345',
        )
        today = timezone.localdate()
        # Bypass Reservation.save()'s full_clean() (2-hour lead time / working
        # hours checks) via bulk_create, since this test only needs a row that
        # exists "today" regardless of the current wall-clock time.
        today_reservation = Reservation(
            user=client_user, service=service, specialist=specialist,
            date=today, time=time_cls(10, 0),
        )
        Reservation.objects.bulk_create([today_reservation])

        # Browse to a different week (next Monday) via the ?week= param.
        other_monday = today + timedelta(days=7)
        while other_monday.weekday() != 0:
            other_monday += timedelta(days=1)

        self.client.force_login(self.specialist_user)
        response = self.client.get(
            reverse('profile_page'), {'week': other_monday.strftime('%Y-%m-%d')},
        )
        self.assertEqual(response.context['bookings_today'], 1)
        self.assertEqual(response.context['next_client_reservation'], today_reservation)

from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from massageProject.main_app.models import Service, Specialist, Reservation, WorkingHours, HomePage
from massageProject.accounts.models import CustomUser
from datetime import datetime, time, date, timedelta

class SchedulingLogicTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            phone_number='0888888888',
            email='test@example.com',
            password='password123'
        )
        self.service_60 = Service.objects.create(
            name='60 min Service',
            description='desc',
            price=50.00,
            duration_in_minutes=60,
            short_description='short'
        )
        self.service_30 = Service.objects.create(
            name='30 min Service',
            description='desc',
            price=30.00,
            duration_in_minutes=30,
            short_description='short'
        )
        self.specialist = Specialist.objects.create(
            name='John Doe',
            description='expert',
            phone_number='0888888889',
            email='john@example.com'
        )
        # John works Monday to Friday, 09:00 - 17:00
        for i in range(5):
            WorkingHours.objects.create(
                specialist=self.specialist,
                day_of_week=i,
                start_time=time(9, 0),
                end_time=time(17, 0)
            )
        
        # We need a date that is a Monday, safely in the future (at least 7
        # days out) so the 2-hour lead time and working-hours checks never
        # collide with "now" as the test suite ages.
        candidate = timezone.localdate() + timedelta(days=7)
        while candidate.weekday() != 0:  # 0 == Monday
            candidate += timedelta(days=1)
        self.test_date = candidate

    def create_reservation(self, service, specialist, date_val, time_val):
        return Reservation.objects.create(
            user=self.user,
            service=service,
            specialist=specialist,
            date=date_val,
            time=time_val
        )

    def test_successful_reservation(self):
        res = self.create_reservation(self.service_60, self.specialist, self.test_date, time(10, 0))
        self.assertEqual(Reservation.objects.count(), 1)

    def test_overlap_exact_same_time(self):
        self.create_reservation(self.service_60, self.specialist, self.test_date, time(10, 0))
        with self.assertRaises(ValidationError) as cm:
            self.create_reservation(self.service_60, self.specialist, self.test_date, time(10, 0))
        self.assertIn("застъпва", str(cm.exception))

    def test_overlap_inside_duration(self):
        # 10:00 - 11:00
        self.create_reservation(self.service_60, self.specialist, self.test_date, time(10, 0))
        # Try 10:30 - 11:00 (overlaps)
        with self.assertRaises(ValidationError):
            self.create_reservation(self.service_30, self.specialist, self.test_date, time(10, 30))

    def test_overlap_end_time_clash(self):
        # 10:00 - 11:00
        self.create_reservation(self.service_60, self.specialist, self.test_date, time(10, 0))
        # Try 09:45 - 10:15 (overlaps)
        with self.assertRaises(ValidationError):
            self.create_reservation(self.service_30, self.specialist, self.test_date, time(9, 45))

    def test_no_overlap_back_to_back(self):
        # 10:00 - 11:00
        self.create_reservation(self.service_60, self.specialist, self.test_date, time(10, 0))
        # 11:00 - 11:30 (should work)
        res2 = self.create_reservation(self.service_30, self.specialist, self.test_date, time(11, 0))
        self.assertEqual(Reservation.objects.count(), 2)

    def test_outside_working_hours_early(self):
        with self.assertRaises(ValidationError) as cm:
            self.create_reservation(self.service_60, self.specialist, self.test_date, time(8, 30))
        self.assertIn("извън работното време", str(cm.exception))

    def test_outside_working_hours_late(self):
        with self.assertRaises(ValidationError):
            self.create_reservation(self.service_60, self.specialist, self.test_date, time(16, 30)) # Ends at 17:30

    def test_not_working_on_weekend(self):
        sunday = self.test_date - timedelta(days=1)
        with self.assertRaises(ValidationError) as cm:
            self.create_reservation(self.service_60, self.specialist, sunday, time(10, 0))
        self.assertIn("не работи в този ден", str(cm.exception))

    def test_lead_time_validation(self):
        # Move "now" to a point where a reservation in 1 hour would fail
        now = timezone.now()
        # Create a date/time just 1 hour from now
        future_1h = now + timedelta(hours=1)
        with self.assertRaises(ValidationError) as cm:
            self.create_reservation(
                self.service_60, 
                self.specialist, 
                future_1h.date(), 
                future_1h.time()
            )
        self.assertIn("поне 2 часа предварително", str(cm.exception))

    def test_different_specialists_same_time(self):
        specialist2 = Specialist.objects.create(
            name='Jane Doe',
            phone_number='0888888880',
            email='jane@example.com'
        )
        WorkingHours.objects.create(
            specialist=specialist2,
            day_of_week=0, # Monday
            start_time=time(9, 0),
            end_time=time(17, 0)
        )
        self.create_reservation(self.service_60, self.specialist, self.test_date, time(10, 0))
        # Jane should be free at 10:00
        self.create_reservation(self.service_60, specialist2, self.test_date, time(10, 0))
        self.assertEqual(Reservation.objects.count(), 2)

class SecurityAndBusinessRulesTest(TestCase):
    def setUp(self):
        self.user1 = CustomUser.objects.create_user(
            phone_number='0888888881', email='u1@e.com', password='p1'
        )
        self.user2 = CustomUser.objects.create_user(
            phone_number='0888888882', email='u2@e.com', password='p2'
        )
        self.service = Service.objects.create(
            name='Service', duration_in_minutes=60, price=50
        )
        self.specialist = Specialist.objects.create(
            name='Specialist', phone_number='0888888883', email='m@e.com'
        )
        # Add working hours for all days to avoid "not working today" errors
        for i in range(7):
            WorkingHours.objects.create(
                specialist=self.specialist, day_of_week=i, 
                start_time=time(0, 0), end_time=time(23, 59)
            )

    def test_edit_other_user_reservation_denied(self):
        future_date = timezone.localdate() + timedelta(days=14)
        res = Reservation.objects.create(
            user=self.user1, service=self.service, specialist=self.specialist,
            date=future_date, time=time(10, 0)
        )
        self.client.login(email='u2@e.com', password='p2')
        response = self.client.get(f'/bg/{res.pk}/edit_reserve/')
        self.assertEqual(response.status_code, 403) # PermissionDenied

    def test_24h_rule_edit(self):
        # Create a reservation for tomorrow
        # But set it to less than 24h from now (e.g. 23h)
        res_datetime = timezone.now() + timedelta(hours=23)
        res = Reservation.objects.create(
            user=self.user1, service=self.service, specialist=self.specialist,
            date=res_datetime.date(), time=res_datetime.time()
        )
        self.client.login(email='u1@e.com', password='p1')
        response = self.client.get(f'/bg/{res.pk}/edit_reserve/')
        self.assertEqual(response.status_code, 302) # Redirect with error
        self.assertRedirects(response, '/bg/profile/')

        # Check for message
        messages = list(response.wsgi_request._messages)
        self.assertTrue(any("24 часа" in str(m) for m in messages))

    def test_24h_rule_delete(self):
        res_datetime = timezone.now() + timedelta(hours=23)
        res = Reservation.objects.create(
            user=self.user1, service=self.service, specialist=self.specialist,
            date=res_datetime.date(), time=res_datetime.time()
        )
        self.client.login(email='u1@e.com', password='p1')
        response = self.client.get(f'/bg/{res.pk}/delete_reserve/')
        self.assertRedirects(response, '/bg/profile/')

    def test_login_required_reservation_page(self):
        response = self.client.get('/bg/reserve/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

class HomePageGetSoloTest(TestCase):
    def test_get_solo_creates_singleton_on_fresh_db(self):
        obj = HomePage.get_solo()
        self.assertIsInstance(obj, HomePage)

    def test_get_solo_returns_same_instance_on_second_call(self):
        first = HomePage.get_solo()
        second = HomePage.get_solo()
        self.assertEqual(first.pk, second.pk)

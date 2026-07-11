from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from massageProject.main_app.models import Massage, Masseur, MessageReservation, WorkingHours
from massageProject.accounts.models import CustomUser
from datetime import datetime, time, date, timedelta

class SchedulingLogicTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            phone_number='0888888888',
            email='test@example.com',
            password='password123'
        )
        self.massage_60 = Massage.objects.create(
            name='60 min Massage',
            description='desc',
            price=50.00,
            duration_in_minutes=60,
            short_description='short'
        )
        self.massage_30 = Massage.objects.create(
            name='30 min Massage',
            description='desc',
            price=30.00,
            duration_in_minutes=30,
            short_description='short'
        )
        self.masseur = Masseur.objects.create(
            name='John Doe',
            description='expert',
            phone_number='0888888889',
            email='john@example.com'
        )
        # John works Monday to Friday, 09:00 - 17:00
        for i in range(5):
            WorkingHours.objects.create(
                masseur=self.masseur,
                day_of_week=i,
                start_time=time(9, 0),
                end_time=time(17, 0)
            )
        
        # We need a fixed date that is a Monday in the future
        # Let's pick 2026-06-08 (Monday)
        self.test_date = date(2026, 6, 8)

    def create_reservation(self, massage, masseur, date_val, time_val):
        return MessageReservation.objects.create(
            user=self.user,
            massage=massage,
            masseur=masseur,
            date=date_val,
            time=time_val
        )

    def test_successful_reservation(self):
        res = self.create_reservation(self.massage_60, self.masseur, self.test_date, time(10, 0))
        self.assertEqual(MessageReservation.objects.count(), 1)

    def test_overlap_exact_same_time(self):
        self.create_reservation(self.massage_60, self.masseur, self.test_date, time(10, 0))
        with self.assertRaises(ValidationError) as cm:
            self.create_reservation(self.massage_60, self.masseur, self.test_date, time(10, 0))
        self.assertIn("застъпва", str(cm.exception))

    def test_overlap_inside_duration(self):
        # 10:00 - 11:00
        self.create_reservation(self.massage_60, self.masseur, self.test_date, time(10, 0))
        # Try 10:30 - 11:00 (overlaps)
        with self.assertRaises(ValidationError):
            self.create_reservation(self.massage_30, self.masseur, self.test_date, time(10, 30))

    def test_overlap_end_time_clash(self):
        # 10:00 - 11:00
        self.create_reservation(self.massage_60, self.masseur, self.test_date, time(10, 0))
        # Try 09:45 - 10:15 (overlaps)
        with self.assertRaises(ValidationError):
            self.create_reservation(self.massage_30, self.masseur, self.test_date, time(9, 45))

    def test_no_overlap_back_to_back(self):
        # 10:00 - 11:00
        self.create_reservation(self.massage_60, self.masseur, self.test_date, time(10, 0))
        # 11:00 - 11:30 (should work)
        res2 = self.create_reservation(self.massage_30, self.masseur, self.test_date, time(11, 0))
        self.assertEqual(MessageReservation.objects.count(), 2)

    def test_outside_working_hours_early(self):
        with self.assertRaises(ValidationError) as cm:
            self.create_reservation(self.massage_60, self.masseur, self.test_date, time(8, 30))
        self.assertIn("извън работното време", str(cm.exception))

    def test_outside_working_hours_late(self):
        with self.assertRaises(ValidationError):
            self.create_reservation(self.massage_60, self.masseur, self.test_date, time(16, 30)) # Ends at 17:30

    def test_not_working_on_weekend(self):
        sunday = date(2026, 6, 7)
        with self.assertRaises(ValidationError) as cm:
            self.create_reservation(self.massage_60, self.masseur, sunday, time(10, 0))
        self.assertIn("не работи в този ден", str(cm.exception))

    def test_lead_time_validation(self):
        # Move "now" to a point where a reservation in 1 hour would fail
        now = timezone.now()
        # Create a date/time just 1 hour from now
        future_1h = now + timedelta(hours=1)
        with self.assertRaises(ValidationError) as cm:
            self.create_reservation(
                self.massage_60, 
                self.masseur, 
                future_1h.date(), 
                future_1h.time()
            )
        self.assertIn("поне 2 часа предварително", str(cm.exception))

    def test_different_masseurs_same_time(self):
        masseur2 = Masseur.objects.create(
            name='Jane Doe',
            phone_number='0888888880',
            email='jane@example.com'
        )
        WorkingHours.objects.create(
            masseur=masseur2,
            day_of_week=0, # Monday
            start_time=time(9, 0),
            end_time=time(17, 0)
        )
        self.create_reservation(self.massage_60, self.masseur, self.test_date, time(10, 0))
        # Jane should be free at 10:00
        self.create_reservation(self.massage_60, masseur2, self.test_date, time(10, 0))
        self.assertEqual(MessageReservation.objects.count(), 2)

class SecurityAndBusinessRulesTest(TestCase):
    def setUp(self):
        self.user1 = CustomUser.objects.create_user(
            phone_number='0888888881', email='u1@e.com', password='p1'
        )
        self.user2 = CustomUser.objects.create_user(
            phone_number='0888888882', email='u2@e.com', password='p2'
        )
        self.massage = Massage.objects.create(
            name='Massage', duration_in_minutes=60, price=50
        )
        self.masseur = Masseur.objects.create(
            name='Masseur', phone_number='0888888883', email='m@e.com'
        )
        # Add working hours for all days to avoid "not working today" errors
        for i in range(7):
            WorkingHours.objects.create(
                masseur=self.masseur, day_of_week=i, 
                start_time=time(0, 0), end_time=time(23, 59)
            )

    def test_edit_other_user_reservation_denied(self):
        res = MessageReservation.objects.create(
            user=self.user1, massage=self.massage, masseur=self.masseur,
            date=date(2026, 6, 15), time=time(10, 0)
        )
        self.client.login(email='u2@e.com', password='p2')
        response = self.client.get(f'/{res.pk}/edit_reserve/')
        self.assertEqual(response.status_code, 403) # PermissionDenied

    def test_24h_rule_edit(self):
        # Create a reservation for tomorrow
        # But set it to less than 24h from now (e.g. 23h)
        res_datetime = timezone.now() + timedelta(hours=23)
        res = MessageReservation.objects.create(
            user=self.user1, massage=self.massage, masseur=self.masseur,
            date=res_datetime.date(), time=res_datetime.time()
        )
        self.client.login(email='u1@e.com', password='p1')
        response = self.client.get(f'/{res.pk}/edit_reserve/')
        self.assertEqual(response.status_code, 302) # Redirect with error
        self.assertRedirects(response, '/profile/')
        
        # Check for message
        messages = list(response.wsgi_request._messages)
        self.assertTrue(any("24 часа" in str(m) for m in messages))

    def test_24h_rule_delete(self):
        res_datetime = timezone.now() + timedelta(hours=23)
        res = MessageReservation.objects.create(
            user=self.user1, massage=self.massage, masseur=self.masseur,
            date=res_datetime.date(), time=res_datetime.time()
        )
        self.client.login(email='u1@e.com', password='p1')
        response = self.client.get(f'/{res.pk}/delete_reserve/')
        self.assertRedirects(response, '/profile/')

    def test_login_required_reservation_page(self):
        response = self.client.get('/reserve/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

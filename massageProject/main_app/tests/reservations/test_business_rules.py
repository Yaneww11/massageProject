from django.test import TestCase
from django.utils import timezone
from massageProject.main_app.models import Service, Specialist, Reservation, WorkingHours
from massageProject.accounts.models import CustomUser
from datetime import time, timedelta


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

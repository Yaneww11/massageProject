from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

from massageProject.main_app.models import Service, Specialist, WorkingHours, Reservation, SiteConfiguration

User = get_user_model()


class BookingEnabledServerEnforcementTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone_number='0888777001', email='bookingflag@example.com',
            password='testpass123', first_name='Test', last_name='User',
        )
        self.specialist = Specialist.objects.create(
            name='Flag Test Specialist', description='desc', phone_number='0888777001',
            email='flagspecialist@example.com',
        )
        self.service = Service.objects.create(
            name='Flag Test Service', description='desc', price=50, duration_in_minutes=60,
            short_description='short',
        )
        WorkingHours.objects.create(
            specialist=self.specialist, day_of_week=(date.today() + timedelta(days=3)).weekday(),
            start_time=time(9, 0), end_time=time(18, 0),
        )
        self.reservation = Reservation.objects.create(
            service=self.service, specialist=self.specialist, user=self.user,
            date=date.today() + timedelta(days=3), time=time(10, 0),
        )
        self.client.force_login(self.user)

    def _disable_booking(self):
        config = SiteConfiguration.get_solo()
        config.booking_enabled = False
        config.save()

    def test_reservation_page_404s_when_booking_disabled(self):
        self._disable_booking()
        response = self.client.get('/bg/reserve/')
        self.assertEqual(response.status_code, 404)

    def test_reservation_page_200s_when_booking_enabled(self):
        response = self.client.get('/bg/reserve/')
        self.assertEqual(response.status_code, 200)

    def test_edit_reservation_404s_when_booking_disabled(self):
        self._disable_booking()
        response = self.client.get(f'/bg/{self.reservation.pk}/edit_reserve/')
        self.assertEqual(response.status_code, 404)

    def test_delete_reservation_404s_when_booking_disabled(self):
        self._disable_booking()
        response = self.client.get(f'/bg/{self.reservation.pk}/delete_reserve/')
        self.assertEqual(response.status_code, 404)

    def test_check_availability_404s_when_booking_disabled(self):
        self._disable_booking()
        response = self.client.get(
            f'/bg/check-availability/?specialist_id={self.specialist.pk}'
            f'&service_id={self.service.pk}&date=2030-01-01'
        )
        self.assertEqual(response.status_code, 404)

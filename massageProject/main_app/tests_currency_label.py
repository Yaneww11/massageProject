from datetime import date, time, timedelta
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from massageProject.main_app.models import Reservation, Service, Specialist, WorkingHours


class ServicesPageCurrencyTest(TestCase):
    def test_services_page_shows_euro_not_leva(self):
        Service.objects.create(
            name='Test Service', description='desc', price=50, duration_in_minutes=60,
            short_description='short',
        )
        response = self.client.get('/bg/services/')
        content = response.content.decode()
        self.assertIn('€', content)
        self.assertNotIn('лв', content)


class ProfilePageCurrencyTest(TestCase):
    def test_profile_page_prices_show_euro_not_leva(self):
        User = get_user_model()
        user = User.objects.create_user(
            phone_number='0888777888', email='currencytest@example.com',
            password='testpass123', first_name='Test', last_name='User',
        )
        specialist = Specialist.objects.create(
            name='Currency Specialist', description='desc', phone_number='0888777888',
            email='currencyspecialist@example.com',
        )
        service = Service.objects.create(
            name='Currency Service', description='desc', price=75, duration_in_minutes=60,
            short_description='short',
        )
        target_date = date.today() + timedelta(days=3)
        WorkingHours.objects.create(
            specialist=specialist, day_of_week=target_date.weekday(),
            start_time=time(9, 0), end_time=time(18, 0),
        )
        Reservation.objects.create(
            service=service, specialist=specialist, user=user,
            date=target_date, time=time(10, 0),
        )
        self.client.force_login(user)
        response = self.client.get('/bg/profile/')
        content = response.content.decode()
        self.assertIn('€', content)
        self.assertNotIn('лв', content)


class ServiceDetailPageCurrencyTest(TestCase):
    def test_service_detail_page_shows_euro_not_leva(self):
        service = Service.objects.create(
            name='Test Service', description='desc', price=50, duration_in_minutes=60,
            short_description='short', image='specialists/measure.jpg',
        )
        response = self.client.get(f'/bg/service/{service.pk}/')
        content = response.content.decode()
        self.assertIn('€', content)
        self.assertNotIn('лв', content)


class ReservationAjaxPriceCurrencyTest(TestCase):
    def test_ajax_reservation_response_shows_euro_not_leva(self):
        User = get_user_model()
        user = User.objects.create_user(
            phone_number='0888999000', email='ajaxcurrencytest@example.com',
            password='testpass123', first_name='Test', last_name='User',
        )
        specialist = Specialist.objects.create(
            name='Ajax Specialist', description='desc', phone_number='0888999000',
            email='ajaxspecialist@example.com',
        )
        service = Service.objects.create(
            name='Ajax Service', description='desc', price=99, duration_in_minutes=60,
            short_description='short',
        )
        target_date = date.today() + timedelta(days=3)
        WorkingHours.objects.create(
            specialist=specialist, day_of_week=target_date.weekday(),
            start_time=time(9, 0), end_time=time(18, 0),
        )
        self.client.force_login(user)
        response = self.client.post('/bg/reserve/', {
            'service': service.pk,
            'specialist': specialist.pk,
            'date': target_date.isoformat(),
            'time': '10:00',
            'additional_text': '',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('€', data['booking']['price'])
        self.assertNotIn('лв', data['booking']['price'])

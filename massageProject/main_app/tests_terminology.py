from django.test import TestCase


class FooterBrandingTest(TestCase):
    def test_footer_copyright_uses_dynamic_brand_name_not_hardcoded_text(self):
        response = self.client.get('/bg/')
        content = response.content.decode()
        self.assertNotIn('Масажно студио Сияние', content)
        self.assertIn('Relax &amp; Health', content)  # demo HomePage.brand_name default


class HeroBrandingTest(TestCase):
    def test_hero_eyebrow_does_not_say_massage_studio(self):
        response = self.client.get('/bg/')
        content = response.content.decode()
        self.assertNotIn('Масажно студио · от 2014', content)
        self.assertIn('Нашето студио · от 2014', content)


class HomeServicesHeadingTest(TestCase):
    def test_home_featured_services_heading_uses_service_plural(self):
        from massageProject.main_app.models import Service
        # Create a service with home_page=True to ensure the section renders
        Service.objects.create(
            name='Test Service', description='desc', price=50, duration_in_minutes=60,
            short_description='short', home_page=True,
        )
        response = self.client.get('/bg/')
        content = response.content.decode()
        self.assertNotIn('Предпочитани масажи', content)
        self.assertIn('Предпочитани услуги', content)  # default service_plural


class ServicesPageSubtitleTest(TestCase):
    def test_services_page_subtitle_does_not_say_massage_procedures(self):
        from massageProject.main_app.models import Service
        # Create a service to ensure the services page renders
        Service.objects.create(
            name='Test Service', description='desc', price=50, duration_in_minutes=60,
            short_description='short',
        )
        response = self.client.get('/bg/services/')
        content = response.content.decode()
        self.assertNotIn('масажни процедури', content)
        self.assertIn('нашите услуги', content)


class ProfileSpecialistRoleLabelTest(TestCase):
    def test_next_booking_specialist_role_uses_specialist_singular(self):
        from datetime import date, time, timedelta
        from django.contrib.auth import get_user_model
        from massageProject.main_app.models import Service, Specialist, WorkingHours, Reservation

        User = get_user_model()
        user = User.objects.create_user(
            phone_number='0888111222', email='profiletest@example.com',
            password='testpass123', first_name='Test', last_name='User',
        )
        specialist = Specialist.objects.create(
            name='Test Specialist', description='desc', phone_number='0888111222',
            email='specialist@example.com',
        )
        service = Service.objects.create(
            name='Test Service', description='desc', price=50, duration_in_minutes=60,
            short_description='short',
        )
        WorkingHours.objects.create(
            specialist=specialist, day_of_week=(date.today() + timedelta(days=2)).weekday(),
            start_time=time(9, 0), end_time=time(18, 0),
        )
        Reservation.objects.create(
            service=service, specialist=specialist, user=user,
            date=date.today() + timedelta(days=2), time=time(10, 0),
        )
        self.client.force_login(user)
        response = self.client.get('/bg/profile/')
        content = response.content.decode()
        self.assertNotIn('>Масажист<', content)
        self.assertIn('>Специалист<', content)  # default specialist_singular, capitalized


class ReservationPageTerminologyTest(TestCase):
    def test_reservation_page_labels_use_terminology_not_massage(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.create_user(
            phone_number='0888333444', email='reservationtest@example.com',
            password='testpass123', first_name='Test', last_name='User',
        )
        self.client.force_login(user)
        response = self.client.get('/bg/reserve/')
        content = response.content.decode()
        self.assertNotIn('>Масаж<', content)
        self.assertNotIn('>Масажист<', content)
        self.assertIn('>Услуга<', content)  # default service_singular, capitalized
        self.assertIn('>Специалист<', content)  # default specialist_singular, capitalized
        self.assertNotIn('Моля, изберете масаж, масажист и дата.', content)
        self.assertNotIn('Типът масаж беше променен', content)

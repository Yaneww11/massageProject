import tempfile
from datetime import date
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from massageProject.main_app.models import BusinessInfo, SiteConfiguration, Specialist, WorkingHours
from massageProject.main_app.models import Service, ServiceGroup
from massageProject.main_app.models import BusinessWorkingHours, HomePage
from massageProject.main_app.models import Comment, Reservation

_MEDIA_ROOT = tempfile.mkdtemp()


def _mocked_get(*args, **kwargs):
    return Mock(status_code=200, content=b'fake-image-bytes')


@override_settings(MEDIA_ROOT=_MEDIA_ROOT)
@patch('massageProject.main_app.management.commands.populate_renkart.requests.get', side_effect=_mocked_get)
class PopulateRenkartCoreDataTest(TestCase):
    def test_creates_site_configuration_business_info_specialist_and_working_hours(self, mock_get):
        call_command('populate_renkart')

        config = SiteConfiguration.get_solo()
        self.assertEqual(config.hero_variant, 'fullbleed')
        self.assertEqual(config.service_singular_bg, 'фотосесия')
        self.assertEqual(config.service_singular_en, 'photo session')
        self.assertEqual(config.specialist_singular_bg, 'фотограф')
        self.assertEqual(config.specialist_singular_en, 'photographer')
        self.assertTrue(config.booking_enabled)
        self.assertTrue(config.comments_enabled)
        self.assertTrue(config.google_login_enabled)

        self.assertEqual(BusinessInfo.objects.count(), 1)
        business_info = BusinessInfo.objects.get()
        self.assertEqual(business_info.name_bg, 'RenkArt')
        self.assertEqual(business_info.email_address, 'art76@abv.bg')
        self.assertTrue(business_info.main_image.name)

        self.assertEqual(Specialist.objects.count(), 1)
        specialist = Specialist.objects.get()
        self.assertEqual(specialist.name_bg, 'Ренета Кирилова')
        self.assertEqual(specialist.name_en, 'Reneta Kirilova')
        self.assertTrue(specialist.image.name)

        self.assertEqual(WorkingHours.objects.filter(specialist=specialist).count(), 5)
        days = set(WorkingHours.objects.filter(specialist=specialist).values_list('day_of_week', flat=True))
        self.assertEqual(days, {1, 2, 3, 4, 5})  # Tue-Sat; closed Sun/Mon

    def test_command_is_idempotent(self, mock_get):
        call_command('populate_renkart')
        call_command('populate_renkart')

        self.assertEqual(BusinessInfo.objects.count(), 1)
        self.assertEqual(Specialist.objects.count(), 1)
        self.assertEqual(WorkingHours.objects.count(), 5)
        self.assertEqual(mock_get.call_count, 4)  # 2 images fetched per run x 2 runs


@override_settings(MEDIA_ROOT=_MEDIA_ROOT)
class PopulateRenkartImageFetchFailureTest(TestCase):
    @patch(
        'massageProject.main_app.management.commands.populate_renkart.requests.get',
        return_value=Mock(status_code=404),
    )
    def test_fetch_image_raises_command_error_on_non_200(self, mock_get):
        with self.assertRaises(CommandError):
            call_command('populate_renkart')


@override_settings(MEDIA_ROOT=_MEDIA_ROOT)
@patch('massageProject.main_app.management.commands.populate_renkart.requests.get', side_effect=_mocked_get)
class PopulateRenkartServicesTest(TestCase):
    def test_creates_three_groups_and_ten_services(self, mock_get):
        call_command('populate_renkart')

        self.assertEqual(ServiceGroup.objects.count(), 3)
        group_names = set(ServiceGroup.objects.values_list('name_bg', flat=True))
        self.assertEqual(group_names, {
            'Портретни фотосесии', 'Fine Art фотосесии', 'Арт / Будоар фотосесии',
        })

        self.assertEqual(Service.objects.count(), 10)
        self.assertEqual(Service.objects.filter(home_page=True).count(), 3)

        mini_studio = Service.objects.get(name_bg='Мини фотосесия в студио')
        self.assertEqual(mini_studio.price, 120)
        self.assertEqual(mini_studio.group.name_bg, 'Портретни фотосесии')
        self.assertTrue(mini_studio.image.name)

        art_session = Service.objects.get(name_bg='Арт / Будоар фотосесия')
        self.assertIn('по договаряне', art_session.short_description_bg)
        self.assertIn('by arrangement', art_session.short_description_en)

    def test_services_idempotent(self, mock_get):
        call_command('populate_renkart')
        call_command('populate_renkart')

        self.assertEqual(ServiceGroup.objects.count(), 3)
        self.assertEqual(Service.objects.count(), 10)


@override_settings(MEDIA_ROOT=_MEDIA_ROOT)
@patch('massageProject.main_app.management.commands.populate_renkart.requests.get', side_effect=_mocked_get)
class PopulateRenkartHomePageTest(TestCase):
    def test_creates_home_page_gallery_image_and_business_hours(self, mock_get):
        call_command('populate_renkart')

        home_page = HomePage.objects.get(pk=1)
        self.assertEqual(home_page.brand_name_bg, 'RenkArt — Портретна и Арт Фотография')
        self.assertEqual(home_page.brand_name_en, 'RenkArt — Portrait & Art Photography')
        self.assertTrue(home_page.logo.name)
        self.assertEqual(home_page.gallery.images.count(), 1)
        self.assertTrue(home_page.gallery.images.first().image.name)

        self.assertEqual(BusinessWorkingHours.objects.filter(home_page=home_page).count(), 2)
        self.assertTrue(
            BusinessWorkingHours.objects.filter(
                home_page=home_page, day_label_bg='Вторник – Събота', hours_bg='10:00 - 18:00',
            ).exists()
        )

    def test_home_page_idempotent(self, mock_get):
        call_command('populate_renkart')
        call_command('populate_renkart')

        self.assertEqual(HomePage.objects.count(), 1)
        home_page = HomePage.objects.get(pk=1)
        self.assertEqual(home_page.gallery.images.count(), 1)
        self.assertEqual(BusinessWorkingHours.objects.filter(home_page=home_page).count(), 2)


@override_settings(MEDIA_ROOT=_MEDIA_ROOT)
@patch('massageProject.main_app.management.commands.populate_renkart.requests.get', side_effect=_mocked_get)
class PopulateRenkartDemoContentTest(TestCase):
    def test_creates_comments_and_reservations(self, mock_get):
        call_command('populate_renkart')

        self.assertEqual(Comment.objects.count(), 5)
        self.assertEqual(Comment.objects.filter(is_reviewed=True).count(), 5)

        self.assertEqual(Reservation.objects.count(), 4)
        self.assertEqual(Reservation.objects.filter(status=Reservation.STATUS_COMPLETED).count(), 2)
        self.assertEqual(Reservation.objects.filter(status=Reservation.STATUS_ACTIVE).count(), 2)

        User = get_user_model()
        self.assertTrue(User.objects.filter(email='demo.client@example.com').exists())

        for reservation in Reservation.objects.filter(status=Reservation.STATUS_ACTIVE):
            self.assertNotIn(reservation.date.weekday(), (0, 6))  # closed Sun/Mon


@override_settings(MEDIA_ROOT=_MEDIA_ROOT)
@patch('massageProject.main_app.management.commands.populate_renkart.requests.get', side_effect=_mocked_get)
class PopulateRenkartFullIdempotencyTest(TestCase):
    def test_full_rerun_does_not_duplicate_anything(self, mock_get):
        from massageProject.main_app.models import (
            BusinessInfo, BusinessWorkingHours, Service, ServiceGroup, SiteConfiguration, Specialist, WorkingHours,
        )

        call_command('populate_renkart')
        call_command('populate_renkart')

        self.assertEqual(BusinessInfo.objects.count(), 1)
        self.assertEqual(Specialist.objects.count(), 1)
        self.assertEqual(WorkingHours.objects.count(), 5)
        self.assertEqual(SiteConfiguration.objects.count(), 1)
        self.assertEqual(ServiceGroup.objects.count(), 3)
        self.assertEqual(Service.objects.count(), 10)
        self.assertEqual(HomePage.objects.count(), 1)
        self.assertEqual(BusinessWorkingHours.objects.count(), 2)
        self.assertEqual(Comment.objects.count(), 5)
        self.assertEqual(Reservation.objects.count(), 4)

import tempfile
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from massageProject.main_app.models import BusinessInfo, SiteConfiguration, Specialist, WorkingHours

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

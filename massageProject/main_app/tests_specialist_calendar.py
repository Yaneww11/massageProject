from django.test import TestCase
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

from massageProject.main_app.models import Specialist, Reservation


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

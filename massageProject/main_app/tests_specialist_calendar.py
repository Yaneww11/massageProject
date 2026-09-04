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


from django.utils import timezone

from massageProject.accounts.models import CustomUser
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

    def test_client_role_renders_existing_sections_not_table(self):
        self.client.force_login(self.plain_user)
        response = self.client.get(reverse('profile_page'))
        self.assertContains(response, 'proof-teaser-card')
        self.assertNotContains(response, 'reservations-table-section')

    def test_specialist_role_renders_table_not_client_sections(self):
        self.client.force_login(self.specialist_user)
        response = self.client.get(reverse('profile_page'))
        self.assertContains(response, 'reservations-table-section')
        self.assertNotContains(response, 'proof-teaser-card')

    def test_staff_role_renders_specialist_filter(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('profile_page'))
        self.assertContains(response, 'id="filter-specialist"')

    def test_specialist_role_does_not_render_specialist_filter(self):
        self.client.force_login(self.specialist_user)
        response = self.client.get(reverse('profile_page'))
        self.assertNotContains(response, 'id="filter-specialist"')

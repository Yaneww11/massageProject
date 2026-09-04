from datetime import time as time_cls, timedelta

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from massageProject.accounts.models import CustomUser
from massageProject.main_app.models import Gallery, Reservation, Service, Specialist, WorkingHours


class SpecialistReservationsTableTestBase(TestCase):
    def setUp(self):
        ct = ContentType.objects.get_for_model(Reservation)
        self.view_all_perm = Permission.objects.get(content_type=ct, codename='view_all_reservations')
        self.view_specialist_perm = Permission.objects.get(content_type=ct, codename='view_specialist_reservations')

        self.service_a = Service.objects.create(
            name='Massage', description='d', price=50, duration_in_minutes=60, short_description='s',
        )
        self.service_b = Service.objects.create(
            name='Photoshoot', description='d', price=150, duration_in_minutes=90, short_description='s',
        )

        self.specialist_user = CustomUser.objects.create_user(
            phone_number='0888600001', email='specialist@example.com', password='pass12345',
        )
        self.specialist = Specialist.objects.create(
            name='Ivan', description='d', phone_number='0888600002', email='ivan@example.com',
            user=self.specialist_user,
        )
        self.specialist_user.user_permissions.add(self.view_specialist_perm)

        self.other_specialist_user = CustomUser.objects.create_user(
            phone_number='0888600003', email='other-specialist@example.com', password='pass12345',
        )
        self.other_specialist = Specialist.objects.create(
            name='Zora', description='d', phone_number='0888600004', email='zora@example.com',
            user=self.other_specialist_user,
        )
        self.other_specialist_user.user_permissions.add(self.view_specialist_perm)

        self.staff_user = CustomUser.objects.create_user(
            phone_number='0888600005', email='staff@example.com', password='pass12345',
        )
        self.staff_user.user_permissions.add(self.view_all_perm)

        self.client_maria = CustomUser.objects.create_user(
            phone_number='0888600006', email='maria@example.com', password='pass12345',
            first_name='Maria', last_name='Petrova',
        )
        self.client_georgi = CustomUser.objects.create_user(
            phone_number='0888600007', email='georgi@example.com', password='pass12345',
            first_name='Georgi', last_name='Ivanov',
        )

        future = timezone.localdate() + timedelta(days=10)
        while future.weekday() != 0:
            future += timedelta(days=1)
        self.future_monday = future
        past = timezone.localdate() - timedelta(days=10)
        while past.weekday() != 0:
            past -= timedelta(days=1)
        self.past_monday = past

        for specialist in (self.specialist, self.other_specialist):
            WorkingHours.objects.create(
                specialist=specialist, day_of_week=0, start_time=time_cls(8, 0), end_time=time_cls(18, 0),
            )

        self.client = Client()

    def _make_reservation(self, specialist, user, service, date, time_, status=Reservation.STATUS_COMPLETED, **extra):
        reservation = Reservation(
            user=user, service=service, specialist=specialist, date=date, time=time_, status=status,
        )
        for key, value in extra.items():
            setattr(reservation, key, value)
        reservation.save()
        return reservation


class TableAccessAndOwnershipTest(SpecialistReservationsTableTestBase):
    def setUp(self):
        super().setUp()
        self.own_reservation = self._make_reservation(
            self.specialist, self.client_maria, self.service_a, self.past_monday, time_cls(10, 0),
        )
        self.other_reservation = self._make_reservation(
            self.other_specialist, self.client_georgi, self.service_a, self.past_monday, time_cls(11, 0),
        )

    def test_specialist_table_renders(self):
        self.client.force_login(self.specialist_user)
        response = self.client.get(reverse('profile_page'))
        self.assertContains(response, 'reservations-table-section')
        self.assertEqual(response.context['role'], 'specialist')

    def test_staff_table_renders(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('profile_page'))
        self.assertContains(response, 'reservations-table-section')
        self.assertEqual(response.context['role'], 'staff')

    def test_specialist_only_sees_own_reservations(self):
        self.client.force_login(self.specialist_user)
        response = self.client.get(reverse('profile_page'))
        reservations = response.context['reservations']
        self.assertIn(self.own_reservation, reservations)
        self.assertNotIn(self.other_reservation, reservations)

    def test_staff_sees_every_specialists_reservations(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('profile_page'))
        reservations = response.context['reservations']
        self.assertIn(self.own_reservation, reservations)
        self.assertIn(self.other_reservation, reservations)

    def test_plain_user_without_permission_gets_client_role_not_table(self):
        plain_user = CustomUser.objects.create_user(
            phone_number='0888600008', email='plain@example.com', password='pass12345',
        )
        self.client.force_login(plain_user)
        response = self.client.get(reverse('profile_page'))
        self.assertEqual(response.context['role'], 'client')
        self.assertNotIn('reservations', response.context)

    def test_soft_deleted_reservation_never_appears(self):
        self.own_reservation.change_status(Reservation.STATUS_DELETED, user=self.specialist_user)
        self.client.force_login(self.specialist_user)
        response = self.client.get(reverse('profile_page'))
        self.assertNotIn(self.own_reservation, response.context['reservations'])


class TableFilterTest(SpecialistReservationsTableTestBase):
    def setUp(self):
        super().setUp()
        self.completed = self._make_reservation(
            self.specialist, self.client_maria, self.service_a, self.past_monday, time_cls(9, 0),
            status=Reservation.STATUS_COMPLETED,
        )
        self.no_show = self._make_reservation(
            self.specialist, self.client_georgi, self.service_b, self.past_monday, time_cls(10, 0),
            status=Reservation.STATUS_NOSHOW,
        )
        self.active = self._make_reservation(
            self.specialist, self.client_maria, self.service_b, self.future_monday, time_cls(9, 0),
            status=Reservation.STATUS_ACTIVE,
        )
        self.client.force_login(self.specialist_user)

    def test_filter_by_status(self):
        response = self.client.get(reverse('profile_page'), {'phase': Reservation.STATUS_NOSHOW})
        reservations = response.context['reservations']
        self.assertEqual(list(reservations), [self.no_show])

    def test_filter_by_date_range(self):
        response = self.client.get(reverse('profile_page'), {
            'date_from': self.future_monday.isoformat(), 'date_to': self.future_monday.isoformat(),
        })
        reservations = response.context['reservations']
        self.assertEqual(list(reservations), [self.active])

    def test_filter_by_service(self):
        response = self.client.get(reverse('profile_page'), {'service_id': self.service_b.pk})
        reservations = response.context['reservations']
        self.assertEqual(set(reservations), {self.no_show, self.active})

    def test_filter_by_client_name_search(self):
        response = self.client.get(reverse('profile_page'), {'q': 'Georgi'})
        reservations = response.context['reservations']
        self.assertEqual(list(reservations), [self.no_show])

    def test_staff_filter_by_specialist(self):
        other_reservation = self._make_reservation(
            self.other_specialist, self.client_maria, self.service_a, self.past_monday, time_cls(9, 0),
        )
        self.client.logout()
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('profile_page'), {'specialist_id': self.specialist.pk})
        reservations = response.context['reservations']
        self.assertNotIn(other_reservation, reservations)
        self.assertIn(self.completed, reservations)

    @override_settings(IS_PHOTOGRAPHER_WEBSITE=False)
    def test_non_photographer_site_offers_only_plain_status_choices(self):
        response = self.client.get(reverse('profile_page'))
        phase_values = {value for value, _label in response.context['phase_choices']}
        self.assertEqual(phase_values, {
            Reservation.STATUS_ACTIVE, Reservation.STATUS_COMPLETED, Reservation.STATUS_NOSHOW,
        })

    @override_settings(IS_PHOTOGRAPHER_WEBSITE=True)
    def test_photographer_site_offers_photo_phase_choices_too(self):
        response = self.client.get(reverse('profile_page'))
        phase_values = {value for value, _label in response.context['phase_choices']}
        self.assertIn(Reservation.PHASE_AWAITING_REVIEW, phase_values)
        self.assertIn(Reservation.STATUS_ACTIVE, phase_values)
        self.assertNotIn(Reservation.STATUS_DELETED, phase_values)


class TableDefaultSortTest(SpecialistReservationsTableTestBase):
    def test_soonest_upcoming_first_then_most_recent_past(self):
        far_future = self.future_monday + timedelta(days=14)
        near_future = self.future_monday
        recent_past = self.past_monday
        older_past = self.past_monday - timedelta(days=30)

        r_far_future = self._make_reservation(
            self.specialist, self.client_maria, self.service_a, far_future, time_cls(9, 0),
            status=Reservation.STATUS_ACTIVE,
        )
        r_near_future = self._make_reservation(
            self.specialist, self.client_maria, self.service_a, near_future, time_cls(9, 0),
            status=Reservation.STATUS_ACTIVE,
        )
        r_recent_past = self._make_reservation(
            self.specialist, self.client_maria, self.service_a, recent_past, time_cls(9, 0),
        )
        r_older_past = self._make_reservation(
            self.specialist, self.client_maria, self.service_a, older_past, time_cls(9, 0),
        )

        self.client.force_login(self.specialist_user)
        response = self.client.get(reverse('profile_page'))
        reservations = list(response.context['reservations'])
        self.assertEqual(reservations, [r_near_future, r_far_future, r_recent_past, r_older_past])


class PhaseQueryModelTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            phone_number='0888600009', email='client-phase@example.com', password='pass12345',
        )
        self.service = Service.objects.create(
            name='Photoshoot', description='d', price=100, duration_in_minutes=60, short_description='s',
        )
        self.specialist = Specialist.objects.create(
            name='Nadia', description='d', phone_number='0888600010', email='nadia@example.com',
        )
        past = timezone.localdate() - timedelta(days=10)
        while past.weekday() != 0:
            past -= timedelta(days=1)
        self.past_monday = past

    def _reservation(self, **extra):
        return Reservation.objects.create(
            user=self.user, service=self.service, specialist=self.specialist,
            date=self.past_monday, time=time_cls(9, 0), status=Reservation.STATUS_COMPLETED, **extra,
        )

    def test_phase_query_matches_computed_property_for_every_phase(self):
        plain = self._reservation()
        gallery_uploaded = self._reservation(gallery=Gallery.objects.create(gallery_type=Gallery.TYPE_PROOFING))
        awaiting_review = self._reservation(
            gallery=Gallery.objects.create(gallery_type=Gallery.TYPE_PROOFING), need_client_review=True,
        )
        editing = self._reservation(
            gallery=Gallery.objects.create(gallery_type=Gallery.TYPE_PROOFING),
            proofing_finalized_at=timezone.now(),
        )
        finals_ready = self._reservation(
            gallery=Gallery.objects.create(gallery_type=Gallery.TYPE_PROOFING),
            proofing_finalized_at=timezone.now(),
            final_gallery=Gallery.objects.create(gallery_type=Gallery.TYPE_FINAL),
        )
        finals_delivered = self._reservation(
            gallery=Gallery.objects.create(gallery_type=Gallery.TYPE_PROOFING),
            proofing_finalized_at=timezone.now(),
            final_gallery=Gallery.objects.create(gallery_type=Gallery.TYPE_FINAL),
            finals_delivered_at=timezone.now(),
        )

        cases = [
            (plain, Reservation.STATUS_COMPLETED),
            (gallery_uploaded, Reservation.PHASE_GALLERY_UPLOADED),
            (awaiting_review, Reservation.PHASE_AWAITING_REVIEW),
            (editing, Reservation.PHASE_EDITING),
            (finals_ready, Reservation.PHASE_FINALS_READY),
            (finals_delivered, Reservation.PHASE_FINALS_DELIVERED),
        ]
        for reservation, phase_value in cases:
            self.assertEqual(reservation.phase, phase_value)
            matched_pks = set(
                Reservation.objects.filter(Reservation.phase_query(phase_value)).values_list('pk', flat=True)
            )
            self.assertIn(reservation.pk, matched_pks, f'phase_query({phase_value!r}) missed its own reservation')
            for other_reservation, other_phase in cases:
                if other_phase != phase_value:
                    self.assertNotIn(
                        other_reservation.pk, matched_pks,
                        f'phase_query({phase_value!r}) wrongly matched a {other_phase!r} reservation',
                    )

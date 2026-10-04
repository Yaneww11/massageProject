import shutil
import tempfile
from datetime import time as time_cls, timedelta

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from massageProject.accounts.models import CustomUser
from massageProject.main_app.models import Gallery, Reservation, Service, Specialist, WorkingHours


from massageProject.main_app.tests.helpers import make_uploaded_jpeg
@override_settings(IS_PHOTOGRAPHER_WEBSITE=True)
class ProofingGalleryUploadViewTest(TestCase):
    def setUp(self):
        self.tmp_media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_media, ignore_errors=True)
        self.storage_override = override_settings(STORAGES={
            'default': {
                'BACKEND': 'django.core.files.storage.FileSystemStorage',
                'OPTIONS': {'location': self.tmp_media, 'base_url': '/media/'},
            },
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
        })
        self.storage_override.enable()
        self.addCleanup(self.storage_override.disable)

        ct = ContentType.objects.get_for_model(Reservation)
        self.view_all_perm = Permission.objects.get(content_type=ct, codename='view_all_reservations')
        self.view_specialist_perm = Permission.objects.get(content_type=ct, codename='view_specialist_reservations')

        self.service = Service.objects.create(
            name='Photoshoot', description='d', price=100, duration_in_minutes=60, short_description='s',
        )
        self.specialist_user = CustomUser.objects.create_user(
            phone_number='0888300001', email='specialist@example.com', password='pass12345',
        )
        self.specialist = Specialist.objects.create(
            name='Ivan', description='d', phone_number='0888300002', email='ivan@example.com',
            user=self.specialist_user,
        )
        self.specialist_user.user_permissions.add(self.view_specialist_perm)

        self.other_specialist = Specialist.objects.create(
            name='Zora (no login)', description='d', phone_number='0888300003', email='zora@example.com',
        )

        self.staff_user = CustomUser.objects.create_user(
            phone_number='0888300004', email='staff@example.com', password='pass12345',
        )
        self.staff_user.user_permissions.add(self.view_all_perm)

        self.client_user = CustomUser.objects.create_user(
            phone_number='0888300005', email='client@example.com', password='pass12345',
            first_name='Maria', last_name='Petrova',
        )

        candidate = timezone.localdate() - timedelta(days=3)
        while candidate.weekday() != 0:
            candidate -= timedelta(days=1)
        self.past_monday = candidate

        self.reservation = Reservation.objects.create(
            user=self.client_user, service=self.service, specialist=self.specialist,
            date=self.past_monday, time=time_cls(10, 0), status=Reservation.STATUS_COMPLETED,
        )
        self.other_reservation = Reservation.objects.create(
            user=self.client_user, service=self.service, specialist=self.other_specialist,
            date=self.past_monday, time=time_cls(11, 0), status=Reservation.STATUS_COMPLETED,
        )

        self.client = Client()
        self.url = reverse('proofing_gallery_upload')

    def _post(self, reservation, images, labels=()):
        data = {
            'reservation': reservation.pk,
            'images': images,
            'labels-TOTAL_FORMS': str(len(labels) or 3),
            'labels-INITIAL_FORMS': '0',
            'labels-MIN_NUM_FORMS': '0',
            'labels-MAX_NUM_FORMS': '1000',
        }
        if labels:
            for i, name in enumerate(labels):
                data[f'labels-{i}-name'] = name
        else:
            for i in range(3):
                data[f'labels-{i}-name'] = ''
        return self.client.post(self.url, data)

    def test_specialist_can_upload_gallery_to_own_reservation(self):
        self.client.force_login(self.specialist_user)
        response = self._post(self.reservation, [make_uploaded_jpeg('a.jpg'), make_uploaded_jpeg('b.jpg')])
        self.assertRedirects(response, reverse('profile_page'))
        self.reservation.refresh_from_db()
        self.assertIsNotNone(self.reservation.gallery_id)
        self.assertEqual(self.reservation.gallery.gallery_type, Gallery.TYPE_PROOFING)
        self.assertEqual(self.reservation.gallery.images.count(), 2)
        self.assertTrue(self.reservation.need_client_review)

    def test_specialist_cannot_upload_to_another_specialists_reservation(self):
        self.client.force_login(self.specialist_user)
        response = self._post(self.other_reservation, [make_uploaded_jpeg('a.jpg')])
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['upload_form'].is_valid())
        self.other_reservation.refresh_from_db()
        self.assertIsNone(self.other_reservation.gallery_id)

    def test_plain_client_is_denied(self):
        self.client.force_login(self.client_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_not_photographer_website_is_404(self):
        with override_settings(IS_PHOTOGRAPHER_WEBSITE=False):
            self.client.force_login(self.specialist_user)
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 404)

    def test_staff_can_upload_on_behalf_of_specialist_with_login(self):
        self.client.force_login(self.staff_user)
        response = self._post(self.reservation, [make_uploaded_jpeg('a.jpg')])
        self.assertRedirects(response, reverse('profile_page'))
        self.reservation.refresh_from_db()
        self.assertIsNotNone(self.reservation.gallery_id)

    def test_staff_can_upload_on_behalf_of_specialist_without_login(self):
        self.client.force_login(self.staff_user)
        response = self._post(self.other_reservation, [make_uploaded_jpeg('a.jpg')])
        self.assertRedirects(response, reverse('profile_page'))
        self.other_reservation.refresh_from_db()
        self.assertIsNotNone(self.other_reservation.gallery_id)

    def test_labels_are_created(self):
        self.client.force_login(self.specialist_user)
        self._post(
            self.reservation, [make_uploaded_jpeg('a.jpg')],
            labels=['За печат', 'Албум'],
        )
        self.reservation.refresh_from_db()
        labels = list(self.reservation.gallery.photo_labels.order_by('order'))
        self.assertEqual([(l.name, l.order) for l in labels], [('За печат', 0), ('Албум', 1)])

    def test_gallery_ready_email_sent_to_client(self):
        self.client.force_login(self.specialist_user)
        self._post(self.reservation, [make_uploaded_jpeg('a.jpg')])
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, [self.client_user.email])
        self.assertIn(reverse('photo_proofing'), email.body)

    def test_reservation_revalidation_failure_on_save_rolls_back_gallery_not_a_500(self):
        # Only STATUS_ACTIVE reservations re-run the working-hours/overlap
        # checks in Reservation.clean() on every save() — construct one, then
        # remove its specialist's working hours so the gallery-attach save()
        # re-validates against a schedule that's since changed.
        future = timezone.localdate() + timedelta(days=7)
        while future.weekday() != 0:
            future += timedelta(days=1)
        WorkingHours.objects.create(
            specialist=self.specialist, day_of_week=0, start_time=time_cls(9, 0), end_time=time_cls(17, 0),
        )
        active_reservation = Reservation.objects.create(
            user=self.client_user, service=self.service, specialist=self.specialist,
            date=future, time=time_cls(10, 0), status=Reservation.STATUS_ACTIVE,
        )
        WorkingHours.objects.filter(specialist=self.specialist, day_of_week=0).delete()

        self.client.force_login(self.specialist_user)
        response = self._post(active_reservation, [make_uploaded_jpeg('a.jpg')])
        self.assertEqual(response.status_code, 200)
        active_reservation.refresh_from_db()
        self.assertIsNone(active_reservation.gallery_id)
        self.assertEqual(Gallery.objects.filter(gallery_type=Gallery.TYPE_PROOFING).count(), 0)

    def _make_reservation_future(self):
        # update() bypasses Reservation.clean(), which would demand working hours.
        Reservation.objects.filter(pk=self.reservation.pk).update(
            date=timezone.localdate() + timedelta(days=1),
        )
        self.reservation.refresh_from_db()

    def test_future_reservation_is_not_offered_in_upload_form(self):
        self._make_reservation_future()
        self.client.force_login(self.specialist_user)
        response = self.client.get(self.url)
        self.assertNotIn(self.reservation, response.context['upload_form'].fields['reservation'].queryset)

    def test_future_reservation_upload_is_rejected(self):
        self._make_reservation_future()
        self.client.force_login(self.specialist_user)
        response = self._post(self.reservation, [make_uploaded_jpeg('a.jpg')])
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['upload_form'].is_valid())
        self.reservation.refresh_from_db()
        self.assertIsNone(self.reservation.gallery_id)

    def test_profile_table_hides_upload_button_for_future_reservation(self):
        self._make_reservation_future()
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('profile_page'))
        self.assertNotContains(response, f'?reservation_id={self.reservation.pk}')
        self.assertContains(response, f'?reservation_id={self.other_reservation.pk}')

import shutil
import tempfile
import zipfile
from datetime import time as time_cls, timedelta
from io import BytesIO

from PIL import Image as PILImage
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from massageProject.accounts.models import CustomUser
from massageProject.main_app.models import Gallery, Reservation, Service, Specialist


def _make_uploaded_image(name='photo.jpg', size=(400, 300), color='green'):
    buffer = BytesIO()
    PILImage.new('RGB', size, color=color).save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


@override_settings(IS_PHOTOGRAPHER_WEBSITE=True)
class FinalGalleryUploadDeliveryTest(TestCase):
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
            phone_number='0888500001', email='specialist@example.com', password='pass12345',
        )
        self.specialist = Specialist.objects.create(
            name='Ivan', description='d', phone_number='0888500002', email='ivan@example.com',
            user=self.specialist_user,
        )
        self.specialist_user.user_permissions.add(self.view_specialist_perm)

        self.staff_user = CustomUser.objects.create_user(
            phone_number='0888500003', email='staff@example.com', password='pass12345',
        )
        self.staff_user.user_permissions.add(self.view_all_perm)

        self.client_user = CustomUser.objects.create_user(
            phone_number='0888500004', email='client@example.com', password='pass12345',
            first_name='Maria', last_name='Petrova',
        )

        candidate = timezone.localdate() - timedelta(days=5)
        while candidate.weekday() != 0:
            candidate -= timedelta(days=1)
        past_monday = candidate

        self.reservation = Reservation.objects.create(
            user=self.client_user, service=self.service, specialist=self.specialist,
            date=past_monday, time=time_cls(10, 0), status=Reservation.STATUS_COMPLETED,
        )

        self.client = Client()
        self.url = reverse('final_gallery_upload')

    def _post(self, reservation, images):
        return self.client.post(self.url, {'reservation': reservation.pk, 'images': images})

    def test_upload_before_finalization_is_rejected(self):
        self.client.force_login(self.specialist_user)
        response = self._post(self.reservation, [_make_uploaded_image()])
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['upload_form'].is_valid())
        self.reservation.refresh_from_db()
        self.assertIsNone(self.reservation.final_gallery_id)

    def test_upload_after_finalization_succeeds(self):
        self.reservation.finalize_proofing()
        self.client.force_login(self.specialist_user)
        response = self._post(self.reservation, [_make_uploaded_image('a.jpg'), _make_uploaded_image('b.jpg')])
        self.assertRedirects(response, reverse('profile_page'))
        self.reservation.refresh_from_db()
        self.assertIsNotNone(self.reservation.final_gallery_id)
        self.assertEqual(self.reservation.final_gallery.gallery_type, Gallery.TYPE_FINAL)
        self.assertEqual(self.reservation.final_gallery.images.count(), 2)
        self.assertIsNotNone(self.reservation.finals_delivered_at)

    def test_staff_can_upload_on_behalf_of_specialist(self):
        self.reservation.finalize_proofing()
        self.client.force_login(self.staff_user)
        response = self._post(self.reservation, [_make_uploaded_image()])
        self.assertRedirects(response, reverse('profile_page'))
        self.reservation.refresh_from_db()
        self.assertIsNotNone(self.reservation.final_gallery_id)

    def test_client_email_sent_with_working_secure_link(self):
        self.reservation.finalize_proofing()
        self.client.force_login(self.specialist_user)
        self._post(self.reservation, [_make_uploaded_image()])
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, [self.client_user.email])
        self.assertIn(reverse('final_gallery_download', args=[self.reservation.pk]), email.body)

        self.client.logout()
        self.client.force_login(self.client_user)
        response = self.client.get(reverse('final_gallery_download', args=[self.reservation.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')

    def test_final_gallery_appears_in_client_profile(self):
        self.reservation.finalize_proofing()
        self.client.force_login(self.specialist_user)
        self._post(self.reservation, [_make_uploaded_image()])

        self.client.logout()
        self.client.force_login(self.client_user)
        response = self.client.get(reverse('profile_page'))
        self.assertContains(response, reverse('final_gallery_download', args=[self.reservation.pk]))

    def test_download_rejects_other_client(self):
        self.reservation.finalize_proofing()
        self.client.force_login(self.specialist_user)
        self._post(self.reservation, [_make_uploaded_image()])

        other_client = CustomUser.objects.create_user(
            phone_number='0888500005', email='other-client@example.com', password='pass12345',
        )
        self.client.logout()
        self.client.force_login(other_client)
        response = self.client.get(reverse('final_gallery_download', args=[self.reservation.pk]))
        self.assertEqual(response.status_code, 404)

    def test_download_404s_before_final_gallery_exists(self):
        self.client.force_login(self.client_user)
        response = self.client.get(reverse('final_gallery_download', args=[self.reservation.pk]))
        self.assertEqual(response.status_code, 404)

    def test_zip_download_contains_uploaded_images(self):
        self.reservation.finalize_proofing()
        self.client.force_login(self.specialist_user)
        self._post(self.reservation, [_make_uploaded_image('a.jpg'), _make_uploaded_image('b.jpg')])

        self.client.logout()
        self.client.force_login(self.client_user)
        response = self.client.get(reverse('final_gallery_download', args=[self.reservation.pk]))
        archive = zipfile.ZipFile(BytesIO(response.content))
        self.assertEqual(len(archive.namelist()), 2)

    def test_not_photographer_website_is_404(self):
        self.reservation.finalize_proofing()
        with override_settings(IS_PHOTOGRAPHER_WEBSITE=False):
            self.client.force_login(self.specialist_user)
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 404)

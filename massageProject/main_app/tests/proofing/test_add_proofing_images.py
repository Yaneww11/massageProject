import os
import shutil
import tempfile
from datetime import time as time_cls, timedelta
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from massageProject.accounts.models import CustomUser
from massageProject.main_app.models import (
    Gallery, Image, ImageProof, Reservation, Service, Specialist,
)
from massageProject.main_app.tests.helpers import make_uploaded_jpeg
from massageProject.main_app.views import ADD_PROOFING_IMAGES_MAX


@override_settings(IS_PHOTOGRAPHER_WEBSITE=True)
class AddProofingImagesTest(TestCase):
    def setUp(self):
        self.tmp_media = tmp_media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_media, ignore_errors=True)
        storage_override = override_settings(STORAGES={
            'default': {
                'BACKEND': 'django.core.files.storage.FileSystemStorage',
                'OPTIONS': {'location': tmp_media, 'base_url': '/media/'},
            },
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
        })
        storage_override.enable()
        self.addCleanup(storage_override.disable)

        ct = ContentType.objects.get_for_model(Reservation)
        specialist_perm = Permission.objects.get(content_type=ct, codename='view_specialist_reservations')
        all_perm = Permission.objects.get(content_type=ct, codename='view_all_reservations')

        service = Service.objects.create(
            name='Photoshoot', description='d', price=100, duration_in_minutes=60, short_description='s',
        )
        self.specialist_user = CustomUser.objects.create_user(
            phone_number='0888400001', email='spec-add@example.com', password='pass12345',
        )
        specialist = Specialist.objects.create(
            name='Ivan', description='d', phone_number='0888400002', email='ivan-add@example.com',
            user=self.specialist_user,
        )
        self.specialist_user.user_permissions.add(specialist_perm)

        self.other_specialist_user = CustomUser.objects.create_user(
            phone_number='0888400003', email='other-add@example.com', password='pass12345',
        )
        Specialist.objects.create(
            name='Zora', description='d', phone_number='0888400004', email='zora-add@example.com',
            user=self.other_specialist_user,
        )
        self.other_specialist_user.user_permissions.add(specialist_perm)

        self.staff_user = CustomUser.objects.create_user(
            phone_number='0888400005', email='staff-add@example.com', password='pass12345',
        )
        self.staff_user.user_permissions.add(all_perm)

        client_user = CustomUser.objects.create_user(
            phone_number='0888400006', email='client-add@example.com', password='pass12345',
        )

        past_monday = timezone.localdate() - timedelta(days=3)
        while past_monday.weekday() != 0:
            past_monday -= timedelta(days=1)

        self.gallery = Gallery.objects.create(
            gallery_type=Gallery.TYPE_PROOFING, published_at=timezone.now(),
        )
        self.reservation = Reservation.objects.create(
            user=client_user, service=service, specialist=specialist,
            date=past_monday, time=time_cls(10, 0), status=Reservation.STATUS_COMPLETED,
        )
        Reservation.all_objects.filter(pk=self.reservation.pk).update(
            gallery=self.gallery, need_client_review=True,
        )
        self.reservation.refresh_from_db()

        self.existing = Image.objects.create(
            gallery=self.gallery, image=make_uploaded_jpeg('existing.jpg'), order=0,
        )
        ImageProof.objects.create(image=self.existing, is_marked=True, comment='love it')

        self.client = Client()
        self.url = reverse('add_proofing_images', args=[self.reservation.pk])

    def _post(self, images, **extra):
        return self.client.post(self.url, {'images': images, **extra})

    def test_specialist_adds_images_after_existing_ones(self):
        self.client.force_login(self.specialist_user)
        response = self._post([make_uploaded_jpeg('a.jpg'), make_uploaded_jpeg('b.jpg')])
        self.assertRedirects(response, reverse('profile_page'), fetch_redirect_response=False)
        images = list(self.gallery.images.order_by('order'))
        self.assertEqual([i.source_name for i in images], ['', 'a.jpg', 'b.jpg'])
        self.assertEqual([i.order for i in images], [0, 1, 2])

    def test_existing_proof_state_is_untouched_and_no_email_sent(self):
        self.client.force_login(self.specialist_user)
        self._post([make_uploaded_jpeg('a.jpg')])
        proof = ImageProof.objects.get(image=self.existing)
        self.assertTrue(proof.is_marked)
        self.assertEqual(proof.comment, 'love it')
        self.assertEqual(len(mail.outbox), 0)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.phase, Reservation.PHASE_AWAITING_REVIEW)

    def test_staff_can_add_images(self):
        self.client.force_login(self.staff_user)
        self._post([make_uploaded_jpeg('a.jpg')])
        self.assertEqual(self.gallery.images.count(), 2)

    def test_other_specialist_is_forbidden(self):
        self.client.force_login(self.other_specialist_user)
        response = self._post([make_uploaded_jpeg('a.jpg')])
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.gallery.images.count(), 1)

    def test_get_is_not_allowed(self):
        self.client.force_login(self.specialist_user)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_not_available_outside_photographer_mode(self):
        self.client.force_login(self.specialist_user)
        with override_settings(IS_PHOTOGRAPHER_WEBSITE=False):
            response = self._post([make_uploaded_jpeg('a.jpg')])
        self.assertEqual(response.status_code, 404)

    def test_rejected_once_client_has_finalized(self):
        self.reservation.finalize_proofing()
        self.client.force_login(self.specialist_user)
        self._post([make_uploaded_jpeg('a.jpg')])
        self.assertEqual(self.gallery.images.count(), 1)

    def test_rejected_when_review_not_requested(self):
        Reservation.all_objects.filter(pk=self.reservation.pk).update(need_client_review=False)
        self.client.force_login(self.specialist_user)
        self._post([make_uploaded_jpeg('a.jpg')])
        self.assertEqual(self.gallery.images.count(), 1)

    def test_more_than_max_is_rejected(self):
        self.client.force_login(self.specialist_user)
        files = [make_uploaded_jpeg(f'{i}.jpg') for i in range(ADD_PROOFING_IMAGES_MAX + 1)]
        self._post(files)
        self.assertEqual(self.gallery.images.count(), 1)

    def test_max_is_accepted(self):
        self.client.force_login(self.specialist_user)
        files = [make_uploaded_jpeg(f'{i}.jpg') for i in range(ADD_PROOFING_IMAGES_MAX)]
        self._post(files)
        self.assertEqual(self.gallery.images.count(), 1 + ADD_PROOFING_IMAGES_MAX)

    def test_one_invalid_file_rejects_whole_batch(self):
        self.client.force_login(self.specialist_user)
        self._post([make_uploaded_jpeg('ok.jpg'), make_uploaded_jpeg('tiny.jpg', size=(100, 100))])
        self.assertEqual(self.gallery.images.count(), 1)

    def test_save_failure_mid_batch_leaves_no_rows_and_no_files(self):
        original = Image.convert_image_field_to_webp
        calls = []

        def fail_on_second(image, field_name):
            calls.append(field_name)
            if len(calls) == 2:
                raise OSError('image file is truncated')
            return original(image, field_name)

        self.client.force_login(self.specialist_user)
        proofing_dir = os.path.join(self.tmp_media, 'reservations', str(self.reservation.pk), 'proofing')
        files_before = set(os.listdir(proofing_dir)) if os.path.isdir(proofing_dir) else set()
        with patch.object(Image, 'convert_image_field_to_webp', fail_on_second), \
                self.assertLogs('massageProject.main_app.views', level='ERROR'):
            response = self._post([make_uploaded_jpeg('a.jpg'), make_uploaded_jpeg('b.jpg')])
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.gallery.images.count(), 1)
        files_after = set(os.listdir(proofing_dir)) if os.path.isdir(proofing_dir) else set()
        self.assertEqual(files_after, files_before)

    def test_cleanup_failure_still_shows_message_instead_of_500(self):
        original = Image.convert_image_field_to_webp
        calls = []

        def fail_on_second(image, field_name):
            calls.append(field_name)
            if len(calls) == 2:
                raise OSError('image file is truncated')
            return original(image, field_name)

        self.client.force_login(self.specialist_user)
        with patch.object(Image, 'convert_image_field_to_webp', fail_on_second), \
                patch('massageProject.main_app.signals.default_storage.delete',
                      side_effect=OSError('gcs down')) as delete, \
                self.assertLogs('massageProject.main_app.views', level='ERROR'):
            response = self._post([make_uploaded_jpeg('a.jpg'), make_uploaded_jpeg('b.jpg')])
        self.assertEqual(response.status_code, 302)
        delete.assert_called_once()
        self.assertEqual(self.gallery.images.count(), 1)

    def test_table_hint_shows_the_server_limit(self):
        self.client.force_login(self.specialist_user)
        with patch('massageProject.main_app.views.ADD_PROOFING_IMAGES_MAX', 7):
            response = self.client.get(reverse('profile_page'))
        self.assertContains(response, 'Изберете до 7 снимки')

    def test_gallery_cap_counts_existing_images(self):
        self.client.force_login(self.specialist_user)
        with patch.dict(Gallery.IMAGE_CAPS, {Gallery.TYPE_PROOFING: 2}):
            self._post([make_uploaded_jpeg('a.jpg'), make_uploaded_jpeg('b.jpg')])
        self.assertEqual(self.gallery.images.count(), 1)

    def test_no_files_is_rejected(self):
        self.client.force_login(self.specialist_user)
        response = self._post([])
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.gallery.images.count(), 1)

    def test_return_query_is_carried_back(self):
        self.client.force_login(self.specialist_user)
        response = self._post([make_uploaded_jpeg('a.jpg')], return_query='phase=awaiting_review')
        self.assertEqual(response['Location'], reverse('profile_page') + '?phase=awaiting_review')

    def test_table_offers_add_images_for_awaiting_review(self):
        self.client.force_login(self.specialist_user)
        response = self.client.get(reverse('profile_page'))
        self.assertContains(response, self.url)

    def test_table_hides_add_images_after_finalizing(self):
        self.reservation.finalize_proofing()
        self.client.force_login(self.specialist_user)
        response = self.client.get(reverse('profile_page'))
        self.assertNotContains(response, self.url)

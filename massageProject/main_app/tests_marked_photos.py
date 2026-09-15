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
from massageProject.main_app.models import Gallery, Image, ImageProof, PhotoLabel, Reservation, Service, Specialist


def _make_uploaded_image(name='photo.jpg', color='red'):
    buffer = BytesIO()
    PILImage.new('RGB', (800, 800), color=color).save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


@override_settings(IS_PHOTOGRAPHER_WEBSITE=True)
class MarkedPhotosTestBase(TestCase):
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
            phone_number='0888400001', email='specialist@example.com', password='pass12345',
        )
        self.specialist = Specialist.objects.create(
            name='Ivan', description='d', phone_number='0888400002', email='ivan-contact@example.com',
            user=self.specialist_user,
        )
        self.specialist_user.user_permissions.add(self.view_specialist_perm)

        self.other_specialist_user = CustomUser.objects.create_user(
            phone_number='0888400003', email='other-specialist@example.com', password='pass12345',
        )
        self.other_specialist = Specialist.objects.create(
            name='Zora', description='d', phone_number='0888400004', email='zora@example.com',
            user=self.other_specialist_user,
        )
        self.other_specialist_user.user_permissions.add(self.view_specialist_perm)

        self.staff_user = CustomUser.objects.create_user(
            phone_number='0888400005', email='staff@example.com', password='pass12345',
        )
        self.staff_user.user_permissions.add(self.view_all_perm)

        self.client_user = CustomUser.objects.create_user(
            phone_number='0888400006', email='client@example.com', password='pass12345',
            first_name='Maria', last_name='Petrova',
        )

        candidate = timezone.localdate() - timedelta(days=3)
        while candidate.weekday() != 0:
            candidate -= timedelta(days=1)
        past_monday = candidate

        self.gallery = Gallery.objects.create(gallery_type=Gallery.TYPE_PROOFING)
        self.marked_image = Image.objects.create(
            gallery=self.gallery, order=0, image=_make_uploaded_image('marked.jpg', 'red'),
        )
        self.unmarked_image = Image.objects.create(
            gallery=self.gallery, order=1, image=_make_uploaded_image('unmarked.jpg', 'blue'),
        )
        self.label = PhotoLabel.objects.create(gallery=self.gallery, name='За печат', order=0)
        proof = ImageProof.objects.create(image=self.marked_image, is_marked=True, comment='crop tighter')
        proof.labels.add(self.label)

        self.reservation = Reservation.objects.create(
            user=self.client_user, service=self.service, specialist=self.specialist,
            date=past_monday, time=time_cls(10, 0), status=Reservation.STATUS_COMPLETED,
            gallery=self.gallery,
        )

        self.client = Client()


class MarkedPhotosViewContentTest(MarkedPhotosTestBase):
    def test_view_shows_only_marked_images_with_labels_and_comment(self):
        self.client.force_login(self.specialist_user)
        response = self.client.get(reverse('marked_photos', args=[self.reservation.pk]))
        self.assertEqual(response.status_code, 200)
        marked_images = response.context['marked_images']
        self.assertEqual(list(marked_images), [self.marked_image])
        self.assertContains(response, 'За печат')
        self.assertContains(response, 'crop tighter')

    def test_specialist_cannot_view_another_specialists_marked_photos(self):
        self.client.force_login(self.other_specialist_user)
        response = self.client.get(reverse('marked_photos', args=[self.reservation.pk]))
        self.assertEqual(response.status_code, 403)

    def test_staff_can_view_on_behalf_of_specialist(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('marked_photos', args=[self.reservation.pk]))
        self.assertEqual(response.status_code, 200)

    def test_not_photographer_website_is_404(self):
        with override_settings(IS_PHOTOGRAPHER_WEBSITE=False):
            self.client.force_login(self.specialist_user)
            response = self.client.get(reverse('marked_photos', args=[self.reservation.pk]))
            self.assertEqual(response.status_code, 404)


class MarkedPhotosDownloadTest(MarkedPhotosTestBase):
    def test_individual_download_returns_original_file(self):
        self.client.force_login(self.specialist_user)
        response = self.client.get(reverse('marked_photo_download', args=[self.reservation.pk, self.marked_image.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Disposition', '').startswith('attachment'), True)

    def test_individual_download_rejects_unmarked_image(self):
        self.client.force_login(self.specialist_user)
        response = self.client.get(reverse('marked_photo_download', args=[self.reservation.pk, self.unmarked_image.pk]))
        self.assertEqual(response.status_code, 404)

    def test_individual_download_rejects_other_specialist(self):
        self.client.force_login(self.other_specialist_user)
        response = self.client.get(reverse('marked_photo_download', args=[self.reservation.pk, self.marked_image.pk]))
        self.assertEqual(response.status_code, 403)

    def test_zip_download_contains_only_marked_images(self):
        self.client.force_login(self.specialist_user)
        response = self.client.get(reverse('marked_photos_zip', args=[self.reservation.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')
        archive = zipfile.ZipFile(BytesIO(response.content))
        self.assertEqual(len(archive.namelist()), 1)

    def test_staff_can_download_on_behalf_of_specialist_without_login(self):
        specialist_no_login = Specialist.objects.create(
            name='No Login', description='d', phone_number='0888400007', email='nologin@example.com',
        )
        self.reservation.specialist = specialist_no_login
        self.reservation.save()
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('marked_photo_download', args=[self.reservation.pk, self.marked_image.pk]))
        self.assertEqual(response.status_code, 200)


class MarksFinalizedEmailTest(MarkedPhotosTestBase):
    def setUp(self):
        super().setUp()
        self.reservation.need_client_review = True
        self.reservation.save(update_fields=['need_client_review'])
        self.client.force_login(self.client_user)

    def test_finalizing_sends_email_to_specialist_contact_address(self):
        response = self.client.post(reverse('photo_proofing_finalize'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.specialist.email])

    def test_finalizing_does_not_send_email_when_not_photographer_website(self):
        with override_settings(IS_PHOTOGRAPHER_WEBSITE=False):
            self.client.post(reverse('photo_proofing_finalize'))
        self.assertEqual(len(mail.outbox), 0)

    def test_calling_finalize_proofing_model_method_directly_does_not_send_email(self):
        # The email trigger lives in the finalize_photo_proofing VIEW, not the
        # model method — existing tests call finalize_proofing() directly and
        # must not start sending mail as a side effect.
        self.reservation.finalize_proofing()
        self.assertEqual(len(mail.outbox), 0)


class MarkedPhotoThumbnailTest(MarkedPhotosTestBase):
    """The Marked Photos grid used to stream the full-size 2560px WebP through
    a gunicorn worker for every thumbnail on the page. It now serves a small
    cached derivative; the download paths still hand over the original."""

    MAX_DIMENSION = 400

    def _thumb_response(self):
        self.client.force_login(self.specialist_user)
        return self.client.get(
            reverse('marked_photo_image', args=[self.reservation.pk, self.marked_image.pk])
        )

    def test_grid_serves_a_small_derivative_not_the_original(self):
        response = self._thumb_response()
        self.assertEqual(response.status_code, 200)
        with PILImage.open(BytesIO(b''.join(response.streaming_content))) as thumb:
            self.assertLessEqual(max(thumb.size), self.MAX_DIMENSION)
        with self.marked_image.image.open('rb') as source:
            with PILImage.open(source) as original:
                self.assertGreater(max(original.size), self.MAX_DIMENSION)

    def test_thumbnail_is_generated_once_and_then_served_from_cache(self):
        from django.core.files.storage import default_storage
        from massageProject.main_app.views import _marked_thumbnail_path

        self._thumb_response()
        path = _marked_thumbnail_path(self.marked_image.pk)
        self.assertTrue(default_storage.exists(path))
        first_mtime = default_storage.get_modified_time(path)
        self._thumb_response()
        self.assertEqual(default_storage.get_modified_time(path), first_mtime)

    def test_thumbnail_carries_no_watermark(self):
        """A flat-colour source stays flat. Lossy WebP shifts a channel by a
        point or two; the watermark composite paints white text over the whole
        frame, which would blow the per-channel spread wide open."""
        response = self._thumb_response()
        with PILImage.open(BytesIO(b''.join(response.streaming_content))) as thumb:
            spread = max(hi - lo for lo, hi in thumb.convert('RGB').getextrema())
        self.assertLess(spread, 16)

    def test_ownership_is_still_enforced_on_the_thumbnail(self):
        self.client.force_login(self.other_specialist_user)
        response = self.client.get(
            reverse('marked_photo_image', args=[self.reservation.pk, self.marked_image.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_unmarked_image_has_no_thumbnail(self):
        self.client.force_login(self.specialist_user)
        response = self.client.get(
            reverse('marked_photo_image', args=[self.reservation.pk, self.unmarked_image.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_individual_download_still_returns_the_full_size_original(self):
        self.client.force_login(self.specialist_user)
        response = self.client.get(
            reverse('marked_photo_download', args=[self.reservation.pk, self.marked_image.pk])
        )
        with PILImage.open(BytesIO(b''.join(response.streaming_content))) as full:
            self.assertGreater(max(full.size), self.MAX_DIMENSION)

    def test_zip_still_contains_full_size_originals(self):
        self.client.force_login(self.specialist_user)
        response = self.client.get(reverse('marked_photos_zip', args=[self.reservation.pk]))
        archive = zipfile.ZipFile(BytesIO(response.content))
        name = archive.namelist()[0]
        with PILImage.open(BytesIO(archive.read(name))) as full:
            self.assertGreater(max(full.size), self.MAX_DIMENSION)

    def test_grid_lazy_loads_thumbnails(self):
        self.client.force_login(self.specialist_user)
        response = self.client.get(reverse('marked_photos', args=[self.reservation.pk]))
        self.assertContains(response, 'loading="lazy"')

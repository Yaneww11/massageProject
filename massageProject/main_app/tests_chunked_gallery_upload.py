"""Ticket 03/04/05 of .scratch/gallery-upload-scale — draft galleries, chunked
upload, explicit publish, resume and caps."""
import json
import shutil
import tempfile
from datetime import time as time_cls, timedelta
from io import BytesIO

from PIL import Image as PILImage
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from massageProject.accounts.models import CustomUser
from massageProject.main_app.models import (
    Gallery, Image, Reservation, Service, Specialist,
)


def _uploaded(name='photo.jpg', size=(800, 800), color='red'):
    buffer = BytesIO()
    PILImage.new('RGB', size, color=color).save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


@override_settings(IS_PHOTOGRAPHER_WEBSITE=True)
class ChunkedUploadTestBase(TestCase):
    url_name = 'proofing_gallery_upload'
    gallery_field = 'gallery'

    def setUp(self):
        # get_cached_homepage() caches a HomePage instance process-wide for a
        # day, and TestCase's rollback does not clear it — a stale entry whose
        # gallery row has been rolled back blows up the home page in whichever
        # test runs next. Keep this module from inheriting or leaving one.
        cache.clear()
        self.addCleanup(cache.clear)
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
        self.view_specialist_perm = Permission.objects.get(
            content_type=ct, codename='view_specialist_reservations')

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

        self.other_specialist_user = CustomUser.objects.create_user(
            phone_number='0888300007', email='zora@example.com', password='pass12345',
        )
        self.other_specialist = Specialist.objects.create(
            name='Zora', description='d', phone_number='0888300003', email='zora2@example.com',
            user=self.other_specialist_user,
        )
        self.other_specialist_user.user_permissions.add(self.view_specialist_perm)

        self.client_user = CustomUser.objects.create_user(
            phone_number='0888300005', email='client@example.com', password='pass12345',
            first_name='Maria', last_name='Petrova',
        )

        candidate = timezone.localdate() - timedelta(days=3)
        while candidate.weekday() != 0:
            candidate -= timedelta(days=1)

        self.reservation = Reservation.objects.create(
            user=self.client_user, service=self.service, specialist=self.specialist,
            date=candidate, time=time_cls(10, 0), status=Reservation.STATUS_COMPLETED,
        )
        self._prepare_reservation()

        self.client = Client()
        self.client.force_login(self.specialist_user)
        self.url = reverse(self.url_name)

    def _prepare_reservation(self):
        pass

    # --- step helpers -------------------------------------------------
    def create_draft(self, reservation=None, labels=()):
        data = {'step': 'create', 'reservation': (reservation or self.reservation).pk}
        for i, name in enumerate(labels):
            data[f'labels-{i}-name'] = name
        data.update({
            'labels-TOTAL_FORMS': str(len(labels) or 3),
            'labels-INITIAL_FORMS': '0',
            'labels-MIN_NUM_FORMS': '0',
            'labels-MAX_NUM_FORMS': '1000',
        })
        return self.client.post(self.url, data)

    def send_chunk(self, gallery_id, images):
        return self.client.post(self.url, {
            'step': 'chunk', 'gallery_id': gallery_id, 'images': images,
        })

    def publish(self, gallery_id):
        return self.client.post(self.url, {'step': 'publish', 'gallery_id': gallery_id})

    def new_draft_id(self, **kwargs):
        return self.create_draft(**kwargs).json()['gallery_id']


class DraftCreationTest(ChunkedUploadTestBase):
    def test_create_returns_a_draft_gallery_and_sends_no_email(self):
        response = self.create_draft()
        self.assertEqual(response.status_code, 200)
        gallery = Gallery.objects.get(pk=response.json()['gallery_id'])
        self.assertEqual(gallery.gallery_type, Gallery.TYPE_PROOFING)
        self.assertEqual(gallery.draft_reservation, self.reservation)
        self.assertIsNone(gallery.published_at)
        self.assertEqual(mail.outbox, [])

    def test_draft_is_not_attached_to_the_reservation_until_publish(self):
        self.create_draft()
        self.reservation.refresh_from_db()
        self.assertIsNone(getattr(self.reservation, f'{self.gallery_field}_id'))

    def test_creating_twice_resumes_the_same_draft(self):
        first = self.new_draft_id()
        second = self.new_draft_id()
        self.assertEqual(first, second)

    def test_create_reports_the_chunk_size_and_cap(self):
        payload = self.create_draft().json()
        self.assertEqual(payload['chunk_size'], 6)
        self.assertEqual(payload['cap'], 400)

    def test_another_specialist_cannot_create_a_draft_for_this_reservation(self):
        self.client.force_login(self.other_specialist_user)
        response = self.create_draft()
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Gallery.objects.filter(draft_reservation=self.reservation).exists())


class ChunkAppendTest(ChunkedUploadTestBase):
    def test_chunk_appends_images_to_the_draft(self):
        gallery_id = self.new_draft_id()
        response = self.send_chunk(gallery_id, [_uploaded('a.jpg'), _uploaded('b.jpg')])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['saved'], 2)
        self.assertEqual(Image.objects.filter(gallery_id=gallery_id).count(), 2)

    def test_order_continues_across_chunks(self):
        gallery_id = self.new_draft_id()
        self.send_chunk(gallery_id, [_uploaded('a.jpg'), _uploaded('b.jpg')])
        self.send_chunk(gallery_id, [_uploaded('c.jpg'), _uploaded('d.jpg')])
        orders = list(Image.objects.filter(gallery_id=gallery_id).order_by('order').values_list('order', flat=True))
        self.assertEqual(orders, [0, 1, 2, 3])

    def test_chunk_records_the_source_filename_and_size(self):
        gallery_id = self.new_draft_id()
        upload = _uploaded('holiday.jpg')
        expected_size = upload.size
        self.send_chunk(gallery_id, [upload])
        image = Image.objects.get(gallery_id=gallery_id)
        self.assertEqual(image.source_name, 'holiday.jpg')
        self.assertEqual(image.source_size, expected_size)
        # The stored file is the converted WebP, which is why the source
        # identity has to be recorded separately.
        self.assertTrue(image.image.name.endswith('.webp'))

    def test_chunk_larger_than_the_configured_size_is_rejected(self):
        gallery_id = self.new_draft_id()
        response = self.send_chunk(gallery_id, [_uploaded(f'{i}.jpg') for i in range(7)])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Image.objects.filter(gallery_id=gallery_id).count(), 0)

    def test_another_specialist_cannot_append_to_this_draft(self):
        gallery_id = self.new_draft_id()
        self.client.force_login(self.other_specialist_user)
        response = self.send_chunk(gallery_id, [_uploaded('a.jpg')])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Image.objects.filter(gallery_id=gallery_id).count(), 0)

    def test_cannot_append_to_a_published_gallery(self):
        gallery_id = self.new_draft_id()
        self.send_chunk(gallery_id, [_uploaded('a.jpg')])
        self.publish(gallery_id)
        response = self.send_chunk(gallery_id, [_uploaded('b.jpg')])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Image.objects.filter(gallery_id=gallery_id).count(), 1)


class PublishTest(ChunkedUploadTestBase):
    def test_publish_attaches_the_gallery_and_sends_exactly_one_email(self):
        gallery_id = self.new_draft_id()
        self.send_chunk(gallery_id, [_uploaded('a.jpg')])
        response = self.publish(gallery_id)
        self.assertEqual(response.status_code, 200)
        self.reservation.refresh_from_db()
        self.assertEqual(getattr(self.reservation, f'{self.gallery_field}_id'), gallery_id)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIsNotNone(Gallery.objects.get(pk=gallery_id).published_at)

    def test_publishing_twice_does_not_send_a_second_email(self):
        gallery_id = self.new_draft_id()
        self.send_chunk(gallery_id, [_uploaded('a.jpg')])
        self.publish(gallery_id)
        self.publish(gallery_id)
        self.assertEqual(len(mail.outbox), 1)

    def test_publishing_an_empty_draft_is_refused(self):
        gallery_id = self.new_draft_id()
        response = self.publish(gallery_id)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(mail.outbox, [])
        self.reservation.refresh_from_db()
        self.assertIsNone(getattr(self.reservation, f'{self.gallery_field}_id'))

    def test_another_specialist_cannot_publish_this_draft(self):
        gallery_id = self.new_draft_id()
        self.send_chunk(gallery_id, [_uploaded('a.jpg')])
        self.client.force_login(self.other_specialist_user)
        response = self.publish(gallery_id)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(mail.outbox, [])


class CapTest(ChunkedUploadTestBase):
    def test_a_chunk_that_would_exceed_the_cap_is_refused_with_no_partial_write(self):
        gallery_id = self.new_draft_id()
        gallery = Gallery.objects.get(pk=gallery_id)
        # Fill to one below the cap without paying for 399 conversions.
        Image.objects.bulk_create([
            Image(gallery=gallery, order=i, image=f'gallery/photos/f{i}.webp')
            for i in range(gallery.image_cap - 1)
        ])
        response = self.send_chunk(gallery_id, [_uploaded('a.jpg'), _uploaded('b.jpg')])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(gallery.images.count(), gallery.image_cap - 1)

    def test_a_chunk_that_exactly_reaches_the_cap_is_accepted(self):
        gallery_id = self.new_draft_id()
        gallery = Gallery.objects.get(pk=gallery_id)
        Image.objects.bulk_create([
            Image(gallery=gallery, order=i, image=f'gallery/photos/f{i}.webp')
            for i in range(gallery.image_cap - 1)
        ])
        response = self.send_chunk(gallery_id, [_uploaded('a.jpg')])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(gallery.images.count(), gallery.image_cap)

    def test_album_and_homepage_galleries_cap_at_fifty(self):
        self.assertEqual(Gallery.IMAGE_CAPS[Gallery.TYPE_ALBUM], 50)
        self.assertEqual(Gallery.IMAGE_CAPS[Gallery.TYPE_HOMEPAGE], 50)
        self.assertEqual(Gallery.IMAGE_CAPS[Gallery.TYPE_PROOFING], 400)
        self.assertEqual(Gallery.IMAGE_CAPS[Gallery.TYPE_FINAL], 400)


class SingleShotStillWorksTest(ChunkedUploadTestBase):
    """The plain form POST is the same create->chunk->publish path in one
    request, so small uploads keep working without JavaScript."""

    def test_plain_form_post_uploads_and_publishes(self):
        response = self.client.post(self.url, {
            'reservation': self.reservation.pk,
            'images': [_uploaded('a.jpg'), _uploaded('b.jpg')],
            'labels-TOTAL_FORMS': '3', 'labels-INITIAL_FORMS': '0',
            'labels-MIN_NUM_FORMS': '0', 'labels-MAX_NUM_FORMS': '1000',
            'labels-0-name': '', 'labels-1-name': '', 'labels-2-name': '',
        })
        self.assertRedirects(response, reverse('profile_page'))
        self.reservation.refresh_from_db()
        gallery = getattr(self.reservation, self.gallery_field)
        self.assertEqual(gallery.images.count(), 2)
        self.assertIsNotNone(gallery.published_at)
        self.assertEqual(len(mail.outbox), 1)


class ResumeTest(ChunkedUploadTestBase):
    """Ticket 04 — an interrupted upload must be resumable without
    re-uploading, and without re-paying for conversions already done."""

    def test_create_reports_what_the_draft_already_holds(self):
        gallery_id = self.new_draft_id()
        self.send_chunk(gallery_id, [_uploaded('a.jpg'), _uploaded('b.jpg')])
        payload = self.create_draft().json()
        self.assertEqual(payload['gallery_id'], gallery_id)
        uploaded = {(entry['name'], entry['size']) for entry in payload['uploaded']}
        self.assertEqual({name for name, _size in uploaded}, {'a.jpg', 'b.jpg'})

    def test_resending_an_already_uploaded_file_is_skipped_not_duplicated(self):
        gallery_id = self.new_draft_id()
        first = _uploaded('a.jpg')
        self.send_chunk(gallery_id, [first])
        again = SimpleUploadedFile('a.jpg', first.file.getvalue(), content_type='image/jpeg')
        response = self.send_chunk(gallery_id, [again])
        self.assertEqual(response.json()['skipped'], 1)
        self.assertEqual(response.json()['saved'], 0)
        self.assertEqual(Image.objects.filter(gallery_id=gallery_id).count(), 1)

    def test_a_different_file_with_the_same_name_is_still_uploaded(self):
        gallery_id = self.new_draft_id()
        self.send_chunk(gallery_id, [_uploaded('DSC_0001.jpg', size=(800, 800), color='red')])
        self.send_chunk(gallery_id, [_uploaded('DSC_0001.jpg', size=(900, 900), color='blue')])
        self.assertEqual(Image.objects.filter(gallery_id=gallery_id).count(), 2)

    def test_a_partial_draft_survives_and_finishes_on_resume(self):
        gallery_id = self.new_draft_id()
        batch = [_uploaded(f'{i}.jpg') for i in range(4)]
        self.send_chunk(gallery_id, batch[:2])
        # ...connection dies here; the photographer reselects the same folder.
        resumed = [SimpleUploadedFile(f.name, f.file.getvalue(), content_type='image/jpeg') for f in batch]
        self.send_chunk(gallery_id, resumed[:2])
        self.send_chunk(gallery_id, resumed[2:])
        self.assertEqual(Image.objects.filter(gallery_id=gallery_id).count(), 4)
        self.publish(gallery_id)
        self.assertEqual(len(mail.outbox), 1)

    def test_photographer_sees_their_own_unpublished_drafts(self):
        gallery_id = self.new_draft_id()
        self.send_chunk(gallery_id, [_uploaded('a.jpg')])
        response = self.client.get(self.url)
        drafts = response.context['drafts']
        self.assertEqual([d.pk for d in drafts], [gallery_id])

    def test_a_published_gallery_is_no_longer_listed_as_a_draft(self):
        gallery_id = self.new_draft_id()
        self.send_chunk(gallery_id, [_uploaded('a.jpg')])
        self.publish(gallery_id)
        response = self.client.get(self.url)
        self.assertEqual(list(response.context['drafts']), [])

    def test_another_specialists_draft_is_not_listed(self):
        gallery_id = self.new_draft_id()
        self.send_chunk(gallery_id, [_uploaded('a.jpg')])
        self.client.force_login(self.other_specialist_user)
        response = self.client.get(self.url)
        self.assertEqual(list(response.context['drafts']), [])

    def test_photographer_can_delete_an_abandoned_draft(self):
        gallery_id = self.new_draft_id()
        self.send_chunk(gallery_id, [_uploaded('a.jpg')])
        response = self.client.post(self.url, {'step': 'discard', 'gallery_id': gallery_id})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Gallery.objects.filter(pk=gallery_id).exists())
        self.assertFalse(Image.objects.filter(gallery_id=gallery_id).exists())

    def test_another_specialist_cannot_delete_this_draft(self):
        gallery_id = self.new_draft_id()
        self.client.force_login(self.other_specialist_user)
        response = self.client.post(self.url, {'step': 'discard', 'gallery_id': gallery_id})
        self.assertEqual(response.status_code, 400)
        self.assertTrue(Gallery.objects.filter(pk=gallery_id).exists())

    def test_a_published_gallery_cannot_be_discarded(self):
        gallery_id = self.new_draft_id()
        self.send_chunk(gallery_id, [_uploaded('a.jpg')])
        self.publish(gallery_id)
        response = self.client.post(self.url, {'step': 'discard', 'gallery_id': gallery_id})
        self.assertEqual(response.status_code, 400)
        self.assertTrue(Gallery.objects.filter(pk=gallery_id).exists())


@override_settings(IS_PHOTOGRAPHER_WEBSITE=True)
class LargeGalleryUploadTest(ChunkedUploadTestBase):
    """Spec verification #1, as far as a test can own it: drive a full gallery
    through the real chunk endpoint and assert the end state.

    Deliberately uses tiny images. This proves chunking, ordering, capping and
    resume at scale; it does NOT validate the 6-per-chunk timing, which was
    sized against a contended 2-vCPU box and cannot be reproduced here.
    """
    IMAGE_COUNT = 400

    def _tiny(self, index):
        # Small enough to convert fast, large enough to clear Image.MIN_DIMENSION.
        return _uploaded(f'DSC_{index:04d}.jpg', size=(600, 600))

    def test_a_full_gallery_uploads_in_chunks_and_publishes_once(self):
        chunk_size = 6
        gallery_id = self.new_draft_id()
        for start in range(0, self.IMAGE_COUNT, chunk_size):
            batch = [self._tiny(i) for i in range(start, min(start + chunk_size, self.IMAGE_COUNT))]
            response = self.send_chunk(gallery_id, batch)
            self.assertEqual(response.status_code, 200, response.content)

        images = Image.objects.filter(gallery_id=gallery_id).order_by('order')
        self.assertEqual(images.count(), self.IMAGE_COUNT)
        self.assertEqual(
            list(images.values_list('order', flat=True)), list(range(self.IMAGE_COUNT)),
            'order must be contiguous across chunks',
        )

        self.assertEqual(mail.outbox, [], 'no email may go out before publish')
        self.publish(gallery_id)
        self.assertEqual(len(mail.outbox), 1)

        self.reservation.refresh_from_db()
        gallery = getattr(self.reservation, self.gallery_field)
        self.assertEqual(gallery.pk, gallery_id)
        self.assertEqual(gallery.images.count(), self.IMAGE_COUNT)

        # The 401st image is refused.
        response = self.send_chunk(gallery_id, [self._tiny(self.IMAGE_COUNT)])
        self.assertEqual(response.status_code, 400)


class FinalGalleryChunkedUploadTest(ChunkedUploadTestBase):
    """The same create -> chunk -> publish path, driven through the final
    gallery view, which collects no labels and sends the delivery email."""
    url_name = 'final_gallery_upload'
    gallery_field = 'final_gallery'

    def _prepare_reservation(self):
        self.reservation.proofing_finalized_at = timezone.now()
        self.reservation.save(update_fields=['proofing_finalized_at'])

    def create_draft(self, reservation=None, labels=()):
        return self.client.post(self.url, {
            'step': 'create', 'reservation': (reservation or self.reservation).pk,
        })

    def test_draft_is_a_final_gallery_and_sends_no_email(self):
        gallery = Gallery.objects.get(pk=self.new_draft_id())
        self.assertEqual(gallery.gallery_type, Gallery.TYPE_FINAL)
        self.assertEqual(mail.outbox, [])

    def test_chunks_then_publish_delivers_once(self):
        gallery_id = self.new_draft_id()
        self.send_chunk(gallery_id, [_uploaded('a.jpg'), _uploaded('b.jpg')])
        self.send_chunk(gallery_id, [_uploaded('c.jpg')])
        self.assertEqual(mail.outbox, [])
        self.publish(gallery_id)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.final_gallery_id, gallery_id)
        self.assertEqual(self.reservation.final_gallery.images.count(), 3)
        self.assertEqual(len(mail.outbox), 1)

    def test_publishing_twice_does_not_deliver_twice(self):
        gallery_id = self.new_draft_id()
        self.send_chunk(gallery_id, [_uploaded('a.jpg')])
        self.publish(gallery_id)
        self.publish(gallery_id)
        self.assertEqual(len(mail.outbox), 1)

    def test_resume_skips_already_uploaded_files(self):
        gallery_id = self.new_draft_id()
        first = _uploaded('a.jpg')
        self.send_chunk(gallery_id, [first])
        again = SimpleUploadedFile('a.jpg', first.file.getvalue(), content_type='image/jpeg')
        response = self.send_chunk(gallery_id, [again])
        self.assertEqual(response.json()['skipped'], 1)
        self.assertEqual(Image.objects.filter(gallery_id=gallery_id).count(), 1)

    def test_another_specialist_cannot_append_to_this_draft(self):
        gallery_id = self.new_draft_id()
        self.client.force_login(self.other_specialist_user)
        response = self.send_chunk(gallery_id, [_uploaded('a.jpg')])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Image.objects.filter(gallery_id=gallery_id).count(), 0)

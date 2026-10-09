import io
import shutil
import tempfile
from collections import Counter
from datetime import time as time_cls, timedelta
from unittest.mock import patch

from django.core.management import call_command

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from massageProject.accounts.models import CustomUser
from massageProject.main_app.models import (
    Gallery, Image, ImageProof, Reservation, Service, Specialist, WorkingHours,
)
from massageProject.main_app.tests.helpers import make_uploaded_jpeg


def _run_purge(*args):
    """The command's own progress lines would otherwise interleave with the
    test runner's output. Returns what it wrote."""
    out = io.StringIO()
    with patch('massageProject.main_app.management.commands.purge_unmarked_proofs.logger'):
        call_command('purge_unmarked_proofs', *args, stdout=out)
    return out.getvalue()


class BucketLayoutBase(TestCase):
    """Real (temporary) filesystem storage: these tests assert on stored keys
    and on blobs actually disappearing, which a mocked storage cannot show."""

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

        self.user = CustomUser.objects.create_user(
            phone_number='0888222111', email='client@example.com', password='pass12345',
        )
        self.service = Service.objects.create(
            name='Shoot', description='d', price=50, duration_in_minutes=60, short_description='s',
        )
        self.specialist = Specialist.objects.create(
            name='Maria', description='d', phone_number='0888222112', email='maria@example.com',
        )
        candidate = timezone.localdate() + timedelta(days=7)
        while candidate.weekday() != 0:
            candidate += timedelta(days=1)
        WorkingHours.objects.create(
            specialist=self.specialist, day_of_week=0,
            start_time=time_cls(9, 0), end_time=time_cls(17, 0),
        )
        self.proofing_gallery = Gallery.objects.create(gallery_type=Gallery.TYPE_PROOFING)
        self.reservation = Reservation.objects.create(
            user=self.user, service=self.service, specialist=self.specialist,
            date=candidate, time=time_cls(10, 0), gallery=self.proofing_gallery,
            need_client_review=True,
        )

    def _add_image(self, gallery, order=0, name='frame.jpg'):
        image = Image(gallery=gallery, image=make_uploaded_jpeg(name), order=order)
        image.save()
        return image


class UploadPathTest(BucketLayoutBase):
    def test_proofing_image_lands_in_the_reservation_folder(self):
        image = self._add_image(self.proofing_gallery)
        self.assertTrue(
            image.image.name.startswith(f'reservations/{self.reservation.pk}/proofing/'),
            image.image.name,
        )

    def test_proofing_image_of_a_draft_gallery_uses_the_draft_reservation(self):
        draft = Gallery.objects.create(
            gallery_type=Gallery.TYPE_PROOFING, draft_reservation=self.reservation,
        )
        image = self._add_image(draft)
        self.assertTrue(
            image.image.name.startswith(f'reservations/{self.reservation.pk}/proofing/'),
            image.image.name,
        )

    def test_album_image_keeps_the_shared_gallery_folder(self):
        album = Gallery.objects.create(gallery_type=Gallery.TYPE_ALBUM, title='Album')
        image = self._add_image(album)
        self.assertTrue(image.image.name.startswith('gallery/photos/'), image.image.name)

    def test_proofing_gallery_without_any_reservation_keeps_the_shared_folder(self):
        orphan = Gallery.objects.create(gallery_type=Gallery.TYPE_PROOFING)
        image = self._add_image(orphan)
        self.assertTrue(image.image.name.startswith('gallery/photos/'), image.image.name)


class PurgeUnmarkedProofsTest(BucketLayoutBase):
    def setUp(self):
        super().setUp()
        self.marked = self._add_image(self.proofing_gallery, order=0, name='keep.jpg')
        self.unmarked = self._add_image(self.proofing_gallery, order=1, name='drop.jpg')
        self.never_opened = self._add_image(self.proofing_gallery, order=2, name='untouched.jpg')
        ImageProof.objects.create(image=self.marked, is_marked=True)
        ImageProof.objects.create(image=self.unmarked, is_marked=False, comment='no')

    def test_purge_keeps_marked_rows_and_drops_the_rest(self):
        deleted = self.reservation.purge_unmarked_proofs()
        self.assertEqual(deleted, 2)
        self.assertEqual(
            list(self.proofing_gallery.images.values_list('pk', flat=True)), [self.marked.pk],
        )

    def test_purge_removes_the_unmarked_originals_from_storage(self):
        unmarked_name = self.unmarked.image.name
        marked_name = self.marked.image.name
        self.reservation.purge_unmarked_proofs()
        self.assertFalse(default_storage.exists(unmarked_name))
        self.assertTrue(default_storage.exists(marked_name))

    def test_purge_removes_the_unmarked_derivatives(self):
        thumbnail = self.unmarked.marked_thumbnail_path
        default_storage.save(thumbnail, SimpleUploadedFile('t.webp', b'x'))
        self.reservation.purge_unmarked_proofs()
        self.assertFalse(default_storage.exists(thumbnail))

    def test_purge_is_idempotent(self):
        self.reservation.purge_unmarked_proofs()
        self.assertEqual(self.reservation.purge_unmarked_proofs(), 0)

    def test_purge_still_stamps_when_the_specialist_hours_no_longer_fit(self):
        """Regression: the stamp used to go through save() -> full_clean(), whose
        working-hours check is not transition-gated. An active reservation whose
        specialist's hours had since changed purged its rows and then raised, so
        the stamp stayed NULL and cron retried the finished purge every hour."""
        self.assertEqual(self.reservation.status, Reservation.STATUS_ACTIVE)
        WorkingHours.objects.all().delete()
        self.reservation.purge_unmarked_proofs()
        self.reservation.refresh_from_db()
        self.assertIsNotNone(self.reservation.proofs_purged_at)
        self.assertEqual(
            list(self.proofing_gallery.images.values_list('pk', flat=True)), [self.marked.pk],
        )

    def test_purge_stamps_the_reservation_as_done(self):
        self.assertIsNone(self.reservation.proofs_purged_at)
        self.reservation.purge_unmarked_proofs()
        self.reservation.refresh_from_db()
        self.assertIsNotNone(self.reservation.proofs_purged_at)

    def test_purge_costs_no_more_than_four_storage_calls_per_photo(self):
        """The purge runs from cron precisely because this number is ~4 and a
        gallery holds up to 400 photos. A regression here — an exists() guard
        creeping back in, say — silently doubles a run that is already minutes
        long against a real bucket, so it is asserted rather than assumed."""
        for image in self.proofing_gallery.images.all():
            default_storage.save(
                f'proof_derivatives/{image.pk}/abc.jpg', SimpleUploadedFile('d.jpg', b'x'),
            )
            default_storage.save(image.marked_thumbnail_path, SimpleUploadedFile('t.webp', b'x'))

        backend = type(default_storage._wrapped)
        watched = ('listdir', 'delete', 'exists')
        calls = Counter()
        originals = {name: getattr(backend, name) for name in watched}

        def counting(name):
            def inner(self, *args, **kwargs):
                calls[name] += 1
                return originals[name](self, *args, **kwargs)
            return inner

        with patch.object(backend, 'listdir', counting('listdir')), \
                patch.object(backend, 'delete', counting('delete')), \
                patch.object(backend, 'exists', counting('exists')):
            purged = self.reservation.purge_unmarked_proofs()

        self.assertEqual(purged, 2)
        self.assertLessEqual(sum(calls.values()) / purged, 4, dict(calls))

    def test_purge_on_a_reservation_without_a_gallery_is_a_no_op(self):
        bare = Reservation.objects.create(
            user=self.user, service=self.service, specialist=self.specialist,
            date=self.reservation.date, time=time_cls(14, 0),
        )
        self.assertEqual(bare.purge_unmarked_proofs(), 0)


class FinalizePurgesTest(BucketLayoutBase):
    def setUp(self):
        super().setUp()
        self.marked = self._add_image(self.proofing_gallery, order=0, name='keep.jpg')
        self.unmarked = self._add_image(self.proofing_gallery, order=1, name='drop.jpg')
        ImageProof.objects.create(image=self.marked, is_marked=True)
        self.client = Client()
        self.client.force_login(self.user)

    def _finalize(self):
        return self.client.post(reverse('photo_proofing_finalize'))

    def test_finalizing_leaves_the_reservation_pending_a_purge(self):
        """The purge is far too slow to run on the request (see the storage-call
        test above); finalising only queues it for the cron command."""
        response = self._finalize()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.reservation.refresh_from_db()
        self.assertTrue(self.reservation.is_proofing_finalized)
        self.assertIsNone(self.reservation.proofs_purged_at)
        self.assertEqual(self.proofing_gallery.images.count(), 2)

    def test_the_command_then_purges_what_finalizing_queued(self):
        self._finalize()
        _run_purge()
        self.assertEqual(
            list(self.proofing_gallery.images.values_list('pk', flat=True)), [self.marked.pk],
        )
        self.reservation.refresh_from_db()
        self.assertIsNotNone(self.reservation.proofs_purged_at)


class PurgeCommandTest(BucketLayoutBase):
    def setUp(self):
        super().setUp()
        self.marked = self._add_image(self.proofing_gallery, order=0, name='keep.jpg')
        self.unmarked = self._add_image(self.proofing_gallery, order=1, name='drop.jpg')
        ImageProof.objects.create(image=self.marked, is_marked=True)

    def test_command_skips_reservations_that_are_not_finalized(self):
        _run_purge()
        self.assertEqual(self.proofing_gallery.images.count(), 2)

    def test_command_skips_reservations_already_stamped_as_purged(self):
        self.reservation.finalize_proofing()
        Reservation.all_objects.filter(pk=self.reservation.pk).update(
            proofs_purged_at=timezone.now(),
        )
        _run_purge()
        self.assertEqual(self.proofing_gallery.images.count(), 2)

    def test_dry_run_reports_without_deleting(self):
        self.reservation.finalize_proofing()
        output = _run_purge('--dry-run')
        self.assertEqual(self.proofing_gallery.images.count(), 2)
        self.assertIn('1 photo(s) to purge', output)
        self.reservation.refresh_from_db()
        self.assertIsNone(self.reservation.proofs_purged_at)

    def test_one_failing_reservation_does_not_abort_the_run(self):
        self.reservation.finalize_proofing()
        other_gallery = Gallery.objects.create(gallery_type=Gallery.TYPE_PROOFING)
        other_unmarked = self._add_image(other_gallery, name='other.jpg')
        other = Reservation.objects.create(
            user=self.user, service=self.service, specialist=self.specialist,
            date=self.reservation.date, time=time_cls(14, 0), gallery=other_gallery,
        )
        other.finalize_proofing()
        real_purge = Reservation.purge_unmarked_proofs
        broken_pk = self.reservation.pk

        def purge_or_fail(reservation):
            if reservation.pk == broken_pk:
                raise OSError('bucket down')
            return real_purge(reservation)

        with patch.object(
            Reservation, 'purge_unmarked_proofs', autospec=True, side_effect=purge_or_fail,
        ):
            _run_purge()

        self.assertTrue(self.proofing_gallery.images.filter(pk=self.unmarked.pk).exists())
        self.assertFalse(other_gallery.images.filter(pk=other_unmarked.pk).exists())

    def test_a_failed_reservation_stays_pending_for_the_next_run(self):
        self.reservation.finalize_proofing()
        with patch.object(
            Reservation, 'purge_unmarked_proofs', side_effect=OSError('bucket down'),
        ):
            _run_purge()
        self.reservation.refresh_from_db()
        self.assertIsNone(self.reservation.proofs_purged_at)
        _run_purge()
        self.reservation.refresh_from_db()
        self.assertIsNotNone(self.reservation.proofs_purged_at)


def _run_thumbnail_purge(*args):
    out = io.StringIO()
    with patch('massageProject.main_app.management.commands.purge_marked_thumbnails.logger'):
        call_command('purge_marked_thumbnails', *args, stdout=out)
    return out.getvalue()


class PurgeMarkedThumbnailsTest(BucketLayoutBase):
    """Marked rows are never deleted, so their cached thumbnail outlives the
    photographer's need for it. Once the reservation is cancelled or its finals
    are delivered, the command clears it."""

    def setUp(self):
        super().setUp()
        self.marked = self._add_image(self.proofing_gallery, name='keep.jpg')
        ImageProof.objects.create(image=self.marked, is_marked=True)
        self.thumbnail = self.marked.marked_thumbnail_path
        default_storage.save(self.thumbnail, SimpleUploadedFile('t.webp', b'x'))

    def _deliver_finals(self):
        Reservation.all_objects.filter(pk=self.reservation.pk).update(
            finals_delivered_at=timezone.now(),
        )

    def test_active_reservation_keeps_its_thumbnails(self):
        _run_thumbnail_purge()
        self.assertTrue(default_storage.exists(self.thumbnail))

    def test_deleted_reservation_loses_its_thumbnails(self):
        Reservation.all_objects.filter(pk=self.reservation.pk).update(
            status=Reservation.STATUS_DELETED,
        )
        _run_thumbnail_purge()
        self.assertFalse(default_storage.exists(self.thumbnail))

    def test_finals_delivered_reservation_loses_its_thumbnails(self):
        self._deliver_finals()
        _run_thumbnail_purge()
        self.assertFalse(default_storage.exists(self.thumbnail))

    def test_the_photos_themselves_are_kept(self):
        self._deliver_finals()
        _run_thumbnail_purge()
        self.assertTrue(default_storage.exists(self.marked.image.name))
        self.assertTrue(Image.objects.filter(pk=self.marked.pk).exists())

    def test_other_reservations_thumbnails_are_untouched(self):
        other_gallery = Gallery.objects.create(gallery_type=Gallery.TYPE_PROOFING)
        Reservation.objects.create(
            user=self.user, service=self.service, specialist=self.specialist,
            date=self.reservation.date, time=time_cls(14, 0), gallery=other_gallery,
        )
        other = self._add_image(other_gallery, name='other.jpg')
        default_storage.save(other.marked_thumbnail_path, SimpleUploadedFile('t.webp', b'x'))
        self._deliver_finals()
        _run_thumbnail_purge()
        self.assertTrue(default_storage.exists(other.marked_thumbnail_path))

    def test_dry_run_reports_without_deleting(self):
        self._deliver_finals()
        output = _run_thumbnail_purge('--dry-run')
        self.assertTrue(default_storage.exists(self.thumbnail))
        self.assertIn('1 thumbnail(s) to purge', output)

    def test_empty_folder_is_a_no_op(self):
        default_storage.delete(self.thumbnail)
        output = _run_thumbnail_purge()
        self.assertIn('Purged 0 thumbnail(s)', output)

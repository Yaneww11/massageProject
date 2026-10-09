import importlib
from datetime import time as time_cls, timedelta
from io import StringIO
from unittest import mock

from django.apps import apps
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.utils import timezone

from massageProject.accounts.models import CustomUser
from massageProject.main_app.models import (
    Gallery, Image, Reservation, Service, Specialist, WorkingHours,
)


class FinalGalleryFixtureMixin:
    """Final galleries can't be created through the model any more, so the
    legacy rows are inserted the way production holds them: raw SQL against the
    pre-migration `gallery_type` value."""

    def _legacy_final_gallery(self, with_reservation=None, images=1):
        gallery = Gallery.objects.create(gallery_type=Gallery.TYPE_ALBUM)
        Gallery.objects.filter(pk=gallery.pk).update(gallery_type='final')
        for n in range(images):
            Image.objects.create(gallery=gallery, order=n, image=f'gallery/legacy-{gallery.pk}-{n}.jpg')
        if with_reservation is not None:
            Gallery.objects.filter(pk=gallery.pk).update(draft_reservation=with_reservation)
        return gallery


class PurgeFinalGalleriesCommandTest(FinalGalleryFixtureMixin, TestCase):
    def setUp(self):
        # The migrated test schema no longer has the column the command meets in production.
        with connection.cursor() as cursor:
            cursor.execute(
                f'ALTER TABLE {Reservation._meta.db_table} ADD COLUMN final_gallery_id integer NULL'
            )
        user = CustomUser.objects.create_user(
            phone_number='0888333331', email='c@example.com', password='pass12345',
        )
        service = Service.objects.create(
            name='Shoot', description='d', price=1, duration_in_minutes=60, short_description='s',
        )
        specialist = Specialist.objects.create(
            name='N', description='d', phone_number='0888333332', email='n@example.com',
        )
        candidate = timezone.localdate() + timedelta(days=7)
        while candidate.weekday() != 0:
            candidate += timedelta(days=1)
        WorkingHours.objects.create(
            specialist=specialist, day_of_week=0, start_time=time_cls(9, 0), end_time=time_cls(17, 0),
        )
        self.reservation = Reservation.objects.create(
            user=user, service=service, specialist=specialist, date=candidate, time=time_cls(10, 0),
        )

    def _run(self, *args):
        out = StringIO()
        call_command('purge_final_galleries', *args, stdout=out)
        return out.getvalue()

    def _attach_ready(self, gallery):
        # Legacy `finals_ready` shape: the gallery is linked, finalized, never emailed.
        with connection.cursor() as cursor:
            cursor.execute(
                'UPDATE main_app_reservation SET final_gallery_id = %s, proofing_finalized_at = %s WHERE id = %s',
                [gallery.pk, timezone.now(), self.reservation.pk],
            )

    def _final_count(self):
        return Gallery.objects.filter(gallery_type='final').count()

    def test_dry_run_deletes_nothing_and_reports(self):
        gallery = self._legacy_final_gallery(images=2)
        self._attach_ready(gallery)
        output = self._run('--dry-run')
        self.assertEqual(self._final_count(), 1)
        self.assertEqual(Image.objects.filter(gallery=gallery).count(), 2)
        self.assertIn('1 final gallery', output)
        self.assertIn(f'reservation {self.reservation.pk}', output)
        self.assertIn('finals_ready', output)
        self.assertIn('1 finals_ready reservation', output)

    def test_real_run_deletes_galleries_images_and_calls_storage_delete(self):
        gallery = self._legacy_final_gallery(images=2)
        self._attach_ready(gallery)
        names = list(Image.objects.filter(gallery=gallery).values_list('image', flat=True))
        with mock.patch('massageProject.main_app.signals.default_storage') as storage:
            storage.listdir.return_value = ([], [])
            self._run()
        self.assertEqual(self._final_count(), 0)
        self.assertFalse(Image.objects.filter(gallery_id=gallery.pk).exists())
        deleted = {c.args[0] for c in storage.delete.call_args_list}
        self.assertTrue(set(names) <= deleted, (names, deleted))

    def test_real_run_reports_finals_ready_loss(self):
        self._attach_ready(self._legacy_final_gallery())
        output = self._run()
        self.assertIn('1 finals_ready reservation', output)

    def test_other_galleries_are_untouched(self):
        proofing = Gallery.objects.create(gallery_type=Gallery.TYPE_PROOFING)
        self._legacy_final_gallery()
        self._run()
        self.assertTrue(Gallery.objects.filter(pk=proofing.pk).exists())

    def test_nothing_to_purge(self):
        self.assertIn('0 final gallery', self._run())


class MigrationGuardTest(FinalGalleryFixtureMixin, TestCase):
    def _guard(self):
        module = importlib.import_module(
            'massageProject.main_app.migrations.0069_remove_stored_finals'
        )
        return module.abort_if_final_galleries_exist

    def test_guard_aborts_while_a_final_gallery_exists(self):
        self._legacy_final_gallery()
        with self.assertRaisesMessage(RuntimeError, 'purge_final_galleries'):
            self._guard()(apps, None)

    def test_guard_passes_once_none_exist(self):
        self._guard()(apps, None)

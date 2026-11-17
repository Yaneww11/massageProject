import shutil
import tempfile
from io import StringIO

from django.core.files.storage import default_storage
from django.core.management import call_command
from django.test import TestCase, override_settings

from massageProject.main_app.models import Gallery, Image
from massageProject.main_app.tests.gallery.test_image_dimensions import make_uploaded_jpeg_with_orientation
from massageProject.main_app.tests.helpers import make_uploaded_jpeg


class BackfillImageDimensionsTest(TestCase):
    def setUp(self):
        self.tmp_media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_media, ignore_errors=True)
        storage_override = override_settings(STORAGES={
            'default': {
                'BACKEND': 'django.core.files.storage.FileSystemStorage',
                'OPTIONS': {'location': self.tmp_media, 'base_url': '/media/'},
            },
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
        })
        storage_override.enable()
        self.addCleanup(storage_override.disable)
        self.gallery = Gallery.objects.create(gallery_type=Gallery.TYPE_HOMEPAGE, title='Home')

    def make_legacy_image(self, name, size):
        image = Image.objects.create(gallery=self.gallery, image=make_uploaded_jpeg(name, size=size))
        # Rows uploaded before dimensions were recorded.
        Image.objects.filter(pk=image.pk).update(width=None, height=None)
        return image

    def run_command(self):
        out = StringIO()
        call_command('backfill_image_dimensions', stdout=out, stderr=StringIO())
        return out.getvalue()

    def test_fills_missing_dimensions_and_leaves_known_ones_untouched(self):
        legacy = self.make_legacy_image('legacy.jpg', size=(900, 600))
        known = Image.objects.create(gallery=self.gallery, image=make_uploaded_jpeg('known.jpg', size=(640, 480)))
        # Deliberately not the file's real size: proves the row is not re-read.
        Image.objects.filter(pk=known.pk).update(width=1, height=2)

        output = self.run_command()

        legacy.refresh_from_db()
        known.refresh_from_db()
        self.assertEqual((legacy.width, legacy.height), (900, 600))
        self.assertEqual((known.width, known.height), (1, 2))
        self.assertIn('1 updated, 1 skipped, 0 failed', output)

    def test_missing_file_is_reported_and_does_not_abort_the_run(self):
        missing = self.make_legacy_image('missing.jpg', size=(800, 800))
        missing.image.storage.delete(missing.image.name)
        present = self.make_legacy_image('present.jpg', size=(700, 1000))

        logger_name = 'massageProject.main_app.management.commands.backfill_image_dimensions'
        with self.assertLogs(logger_name, level='WARNING') as logs:
            output = self.run_command()

        self.assertIn(missing.image.name, logs.output[0])
        missing.refresh_from_db()
        present.refresh_from_db()
        self.assertEqual((missing.width, missing.height), (None, None))
        self.assertEqual((present.width, present.height), (700, 1000))
        self.assertIn('1 updated, 0 skipped, 1 failed', output)

    def test_never_converted_file_with_exif_rotation_gets_stored_dimensions(self):
        # A legacy JPEG stored as-is (no WebP conversion): landscape pixels
        # with EXIF orientation 6. The proof derivative is generated without
        # exif_transpose and without EXIF, so it keeps the raw pixel
        # orientation; the dimensions must describe the stored file.
        name = default_storage.save(
            'gallery/photos/rotated.jpg', make_uploaded_jpeg_with_orientation('rotated.jpg', (300, 200), 6),
        )
        image = Image.objects.create(gallery=self.gallery, image=name)

        self.run_command()

        image.refresh_from_db()
        self.assertEqual((image.width, image.height), (300, 200))

    def test_second_run_changes_nothing(self):
        image = self.make_legacy_image('legacy.jpg', size=(900, 600))
        self.run_command()

        output = self.run_command()

        image.refresh_from_db()
        self.assertEqual((image.width, image.height), (900, 600))
        self.assertIn('0 updated, 1 skipped, 0 failed', output)

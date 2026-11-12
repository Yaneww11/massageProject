import shutil
import tempfile
from io import BytesIO
from unittest import mock

from PIL import Image as PILImage
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from massageProject.main_app.models import Gallery, Image
from massageProject.main_app.tests.helpers import make_uploaded_jpeg


def make_uploaded_jpeg_with_orientation(name, size, orientation):
    buffer = BytesIO()
    exif = PILImage.Exif()
    exif[0x0112] = orientation
    PILImage.new('RGB', size, color='blue').save(buffer, format='JPEG', exif=exif)
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


class ImageDimensionsTest(TestCase):
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
        self.gallery = Gallery.objects.create(gallery_type=Gallery.TYPE_HOMEPAGE, title='Home')

    def test_loading_image_with_unknown_dimensions_does_not_open_the_file(self):
        image = Image.objects.create(gallery=self.gallery, image=make_uploaded_jpeg('legacy.jpg'))
        # Legacy rows predate the dimension fields and live on remote storage.
        Image.objects.filter(pk=image.pk).update(width=None, height=None)

        with mock.patch.object(
            FileSystemStorage, 'open', autospec=True, side_effect=FileSystemStorage.open,
        ) as storage_open:
            loaded = Image.objects.get(pk=image.pk)

        storage_open.assert_not_called()
        self.assertIsNone(loaded.width)
        self.assertIsNone(loaded.height)

    def test_exif_rotated_upload_stores_transposed_dimensions(self):
        # Stored landscape, but EXIF orientation 6 means "rotate 90° to display": a portrait.
        upload = make_uploaded_jpeg_with_orientation('rotated.jpg', size=(300, 200), orientation=6)
        image = Image.objects.create(gallery=self.gallery, image=upload)
        image.refresh_from_db()
        self.assertEqual((image.width, image.height), (200, 300))

    def test_resaving_without_a_new_file_does_not_reread_it(self):
        image = Image.objects.create(gallery=self.gallery, image=make_uploaded_jpeg('a.jpg', size=(640, 480)))
        image = Image.objects.get(pk=image.pk)

        with mock.patch.object(
            FileSystemStorage, 'open', autospec=True, side_effect=FileSystemStorage.open,
        ) as storage_open:
            image.alt_text = 'Renamed'
            image.save()

        storage_open.assert_not_called()
        image.refresh_from_db()
        self.assertEqual((image.width, image.height), (640, 480))

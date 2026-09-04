import shutil
import tempfile
from io import BytesIO

from PIL import Image as PILImage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from massageProject.main_app.models import Gallery, HomePage, Service


def _make_uploaded_png(name, mode, size=(100, 100)):
    buffer = BytesIO()
    if mode == 'P':
        img = PILImage.new('RGBA', size, (255, 0, 0, 0))
        img = img.convert('P', palette=PILImage.ADAPTIVE)
        img.info['transparency'] = 0
    else:
        img = PILImage.new(mode, size, (255, 0, 0, 0) if mode == 'RGBA' else (255, 0))
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/png')


class WebpConversionAlphaTest(TestCase):
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

    def test_palette_mode_transparency_is_preserved_as_webp(self):
        gallery = Gallery.objects.create(gallery_type=Gallery.TYPE_HOMEPAGE, title='Home')
        upload = _make_uploaded_png('logo.png', mode='P')
        home_page = HomePage.objects.create(brand_name='Studio', description='desc', gallery=gallery, logo=upload)
        with PILImage.open(home_page.logo.path) as saved:
            self.assertEqual(saved.mode, 'RGBA')
            self.assertEqual(saved.getpixel((0, 0))[3], 0)

    def test_rgba_transparency_is_preserved_as_webp(self):
        upload = _make_uploaded_png('service.png', mode='RGBA')
        service = Service.objects.create(
            name='Massage', description='d', price=10, duration_in_minutes=30,
            short_description='sd', image=upload,
        )
        with PILImage.open(service.image.path) as saved:
            self.assertEqual(saved.mode, 'RGBA')
            self.assertEqual(saved.getpixel((0, 0))[3], 0)

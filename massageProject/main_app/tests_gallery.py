import shutil
import tempfile
from io import BytesIO

from PIL import Image as PILImage
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from massageProject.main_app.models import Gallery, Image


class GalleryCleanTest(TestCase):
    def test_second_homepage_gallery_is_rejected(self):
        Gallery.objects.create(gallery_type=Gallery.TYPE_HOMEPAGE, title='Home')
        second = Gallery(gallery_type=Gallery.TYPE_HOMEPAGE, title='Home 2')
        with self.assertRaises(ValidationError):
            second.full_clean()

    def test_editing_the_existing_homepage_gallery_is_allowed(self):
        gallery = Gallery.objects.create(gallery_type=Gallery.TYPE_HOMEPAGE, title='Home')
        gallery.title = 'Renamed'
        gallery.full_clean()

    def test_album_without_title_is_rejected(self):
        album = Gallery(gallery_type=Gallery.TYPE_ALBUM, slug='no-title')
        with self.assertRaises(ValidationError):
            album.full_clean()

    def test_album_with_title_is_valid(self):
        album = Gallery(gallery_type=Gallery.TYPE_ALBUM, title='Studio', slug='studio')
        album.full_clean()


class GalleryViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.album = Gallery.objects.create(
            gallery_type=Gallery.TYPE_ALBUM, title='Studio Tour', slug='studio-tour',
        )
        Image.objects.create(gallery=self.album, order=0, alt_text='Front desk', image='gallery/test.jpg')
        # A non-album gallery must not appear on the public gallery listing.
        Gallery.objects.create(gallery_type=Gallery.TYPE_HOMEPAGE, title='Home')

    def test_gallery_list_shows_only_album_galleries(self):
        response = self.client.get(reverse('gallery'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['albums']), [self.album])

    def test_gallery_album_detail_renders(self):
        response = self.client.get(reverse('gallery_album', args=[self.album.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['photos']), list(self.album.images.all()))

    def test_gallery_album_detail_404_for_non_album_gallery(self):
        homepage_gallery = Gallery.objects.get(gallery_type=Gallery.TYPE_HOMEPAGE)
        homepage_gallery.slug = 'home'
        homepage_gallery.save()
        response = self.client.get(reverse('gallery_album', args=['home']))
        self.assertEqual(response.status_code, 404)


def _make_uploaded_image(name='photo.jpg', size=(800, 800)):
    buffer = BytesIO()
    PILImage.new('RGB', size, color='red').save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


def _make_uploaded_image_with_orientation(name, size, orientation):
    buffer = BytesIO()
    img = PILImage.new('RGB', size, color='blue')
    exif = img.getexif()
    exif[0x0112] = orientation
    img.save(buffer, format='JPEG', exif=exif.tobytes())
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


class GalleryBulkUploadAdminTest(TestCase):
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

        self.client = Client()
        User = get_user_model()
        self.admin_user = User.objects.create_superuser(
            email='gallery-bulk-admin@example.com', phone_number='0888888897', password='testpass123',
        )
        self.client.force_login(self.admin_user)
        self.gallery = Gallery.objects.create(
            gallery_type=Gallery.TYPE_ALBUM, title='Session', slug='session',
        )
        self.url = reverse('admin:main_app_gallery_bulk_upload_images', args=[self.gallery.pk])
        self.change_url = reverse('admin:main_app_gallery_change', args=[self.gallery.pk])

    def test_get_renders_upload_form(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<form')

    def test_post_multiple_valid_images_creates_rows_in_order(self):
        files = [_make_uploaded_image(f'photo{i}.jpg') for i in range(3)]
        response = self.client.post(self.url, {'images': files})
        self.assertRedirects(response, self.change_url)
        images = list(self.gallery.images.order_by('order'))
        self.assertEqual(len(images), 3)
        self.assertEqual([img.order for img in images], [0, 1, 2])
        self.assertTrue(all(img.alt_text == '' for img in images))

    def test_next_order_continues_after_existing_images_regardless_of_gaps(self):
        Image.objects.create(gallery=self.gallery, image=_make_uploaded_image('existing.jpg'), order=7)
        response = self.client.post(self.url, {'images': [_make_uploaded_image('new.jpg')]})
        self.assertRedirects(response, self.change_url)
        new_image = self.gallery.images.order_by('-order').first()
        self.assertEqual(new_image.order, 8)

    def test_post_skips_invalid_file_and_uploads_the_rest(self):
        good = _make_uploaded_image('good.jpg')
        bad = SimpleUploadedFile('bad.txt', b'not an image', content_type='text/plain')
        response = self.client.post(self.url, {'images': [good, bad]})
        self.assertRedirects(response, self.change_url)
        self.assertEqual(self.gallery.images.count(), 1)
        messages_list = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any('bad.txt' in m for m in messages_list))

    def test_post_with_no_files_shows_validation_error_and_creates_nothing(self):
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['form'].is_valid())
        self.assertEqual(self.gallery.images.count(), 0)

    def test_non_staff_user_is_redirected_to_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_staff_without_change_permission_is_denied(self):
        no_perm_user = get_user_model().objects.create_user(
            email='gallery-no-perm@example.com', phone_number='0888888896',
            password='testpass123', is_staff=True,
        )
        self.client.logout()
        self.client.force_login(no_perm_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)


class ImageProcessingTest(TestCase):
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
        self.gallery = Gallery.objects.create(gallery_type=Gallery.TYPE_ALBUM, title='Studio', slug='studio')

    def test_large_image_is_downscaled_to_max_dimension(self):
        upload = _make_uploaded_image('big.jpg', size=(4000, 3000))
        image = Image.objects.create(gallery=self.gallery, image=upload)
        with PILImage.open(image.image.path) as saved:
            self.assertEqual(max(saved.size), 2560)

    def test_image_within_limits_is_not_upscaled(self):
        upload = _make_uploaded_image('small_ok.jpg', size=(800, 800))
        image = Image.objects.create(gallery=self.gallery, image=upload)
        with PILImage.open(image.image.path) as saved:
            self.assertEqual(saved.size, (800, 800))

    def test_uploaded_image_is_converted_to_webp(self):
        upload = _make_uploaded_image('photo.jpg', size=(800, 800))
        image = Image.objects.create(gallery=self.gallery, image=upload)
        self.assertTrue(image.image.name.endswith('.webp'))
        with PILImage.open(image.image.path) as saved:
            self.assertEqual(saved.format, 'WEBP')

    def test_exif_orientation_is_applied_before_saving(self):
        upload = _make_uploaded_image_with_orientation('rotated.jpg', size=(1200, 800), orientation=6)
        image = Image.objects.create(gallery=self.gallery, image=upload)
        with PILImage.open(image.image.path) as saved:
            self.assertEqual(saved.size, (800, 1200))

    def test_image_below_minimum_dimension_is_rejected(self):
        upload = _make_uploaded_image('tiny.jpg', size=(300, 300))
        image = Image(gallery=self.gallery, image=upload)
        with self.assertRaises(ValidationError):
            image.full_clean()

    def test_crop_position_defaults_to_center(self):
        upload = _make_uploaded_image('photo.jpg')
        image = Image.objects.create(gallery=self.gallery, image=upload)
        self.assertEqual(image.crop_position, Image.CROP_CENTER)

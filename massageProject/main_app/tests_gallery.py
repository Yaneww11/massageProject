from django.core.exceptions import ValidationError
from django.test import Client, TestCase
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

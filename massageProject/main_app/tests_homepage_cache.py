"""The cached HomePage singleton and its required gallery.

get_cached_homepage() stores a HomePage *instance* — a model object with a
required OneToOne to Gallery. Two things follow that the original code did not
account for:

* HomePage.gallery is on_delete=CASCADE, so deleting the gallery deletes the
  HomePage row. Only post_save invalidated the cache, so the entry survived its
  own row and every later page render raised Gallery.DoesNotExist.
* The signal only clears the cache in the worker that handled the write. In a
  multi-worker deploy another worker keeps serving the stale instance until the
  entry expires, so the render has to survive one.
"""
from django.core.cache import cache
from django.test import Client, TestCase

from massageProject.main_app.context_processors import (
    HOMEPAGE_CACHE_KEY, SINGLETON_CACHE_TTL, get_cached_homepage,
)
from massageProject.main_app.models import Gallery, HomePage


class HomePageCacheInvalidationTest(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.gallery = Gallery.objects.create(gallery_type=Gallery.TYPE_HOMEPAGE)
        # pk=1 is what HomePage.get_solo() resolves, so build the singleton the
        # way production does rather than an incidental second row.
        self.homepage = HomePage.objects.create(
            pk=1, brand_name='Studio', description='d', gallery=self.gallery,
        )

    def test_saving_the_homepage_invalidates_the_cache(self):
        get_cached_homepage()
        self.assertIsNotNone(cache.get(HOMEPAGE_CACHE_KEY))
        self.homepage.brand_name = 'Renamed'
        self.homepage.save()
        self.assertIsNone(cache.get(HOMEPAGE_CACHE_KEY))

    def test_deleting_the_homepage_invalidates_the_cache(self):
        get_cached_homepage()
        self.homepage.delete()
        self.assertIsNone(cache.get(HOMEPAGE_CACHE_KEY))

    def test_deleting_the_gallery_invalidates_the_cascaded_homepage(self):
        """The gallery is the cascade root: deleting it takes the HomePage row
        with it, so the cached instance must go too."""
        get_cached_homepage()
        self.gallery.delete()
        self.assertFalse(HomePage.objects.exists())
        self.assertIsNone(cache.get(HOMEPAGE_CACHE_KEY))

    def test_ttl_matches_the_documented_cross_worker_staleness_bound(self):
        """The bound the comment always claimed. At 86400s another worker could
        serve a deleted homepage for a day."""
        self.assertEqual(SINGLETON_CACHE_TTL, 60)


class StaleHomePageCacheRenderTest(TestCase):
    """A stale entry is unavoidable across workers within the TTL, so rendering
    must degrade rather than 500."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.client = Client()

    def _poison_cache_with_a_deleted_homepage(self):
        gallery = Gallery.objects.create(gallery_type=Gallery.TYPE_HOMEPAGE)
        homepage = HomePage.objects.create(
            pk=1, brand_name='Studio', description='d', gallery=gallery,
        )
        stale = HomePage.objects.get(pk=homepage.pk)
        gallery.delete()  # cascades the HomePage row away
        # Stand in for a second worker that never saw the invalidation.
        cache.set(HOMEPAGE_CACHE_KEY, stale, 60)
        return stale

    def test_home_page_renders_without_its_gallery_instead_of_erroring(self):
        self._poison_cache_with_a_deleted_homepage()
        response = self.client.get('/bg/')
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['gallery'])
        self.assertEqual(list(response.context['gallery_images']), [])

    def test_a_homepage_with_a_live_gallery_still_renders_its_carousel(self):
        gallery = Gallery.objects.create(gallery_type=Gallery.TYPE_HOMEPAGE)
        HomePage.objects.create(pk=1, brand_name='Studio', description='d', gallery=gallery)
        response = self.client.get('/bg/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['gallery'], gallery)

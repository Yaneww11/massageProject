from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver

from massageProject.main_app.context_processors import BUSINESS_INFO_CACHE_KEY, HOMEPAGE_CACHE_KEY
from massageProject.main_app.models import BusinessInfo, HomePage, SiteConfiguration


@receiver(post_save, sender=SiteConfiguration)
def invalidate_site_configuration_cache(sender, **kwargs):
    cache.delete('site_configuration')


@receiver(post_save, sender=HomePage)
def invalidate_homepage_cache(sender, **kwargs):
    cache.delete(HOMEPAGE_CACHE_KEY)


@receiver(post_save, sender=BusinessInfo)
def invalidate_business_info_cache(sender, **kwargs):
    cache.delete(BUSINESS_INFO_CACHE_KEY)

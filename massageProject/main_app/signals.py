import logging

from django.core.cache import cache
from django.core.files.storage import default_storage
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from massageProject.main_app.context_processors import BUSINESS_INFO_CACHE_KEY, HOMEPAGE_CACHE_KEY
from massageProject.main_app.models import BusinessInfo, HomePage, Image, SiteConfiguration

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Image)
def clear_proof_derivatives_on_image_change(sender, instance, **kwargs):
    """Photo proofing derivatives are cached per (image, user); if an admin replaces
    the original file, stale derivatives must be cleared so they regenerate."""
    if not instance.pk:
        return
    try:
        old_instance = Image.objects.get(pk=instance.pk)
    except Image.DoesNotExist:
        return
    old_name = old_instance.image.name if old_instance.image else None
    new_name = instance.image.name if instance.image else None
    if old_name == new_name:
        return
    prefix = f'proof_derivatives/{instance.pk}/'
    try:
        _, filenames = default_storage.listdir(prefix)
    except (FileNotFoundError, NotADirectoryError):
        return
    for filename in filenames:
        default_storage.delete(prefix + filename)


@receiver(post_save, sender=SiteConfiguration)
def invalidate_site_configuration_cache(sender, **kwargs):
    cache.delete('site_configuration')


@receiver(post_save, sender=HomePage)
def invalidate_homepage_cache(sender, **kwargs):
    cache.delete(HOMEPAGE_CACHE_KEY)


@receiver(post_save, sender=BusinessInfo)
def invalidate_business_info_cache(sender, **kwargs):
    cache.delete(BUSINESS_INFO_CACHE_KEY)

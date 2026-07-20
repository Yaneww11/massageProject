from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver

from massageProject.main_app.models import SiteConfiguration


@receiver(post_save, sender=SiteConfiguration)
def invalidate_site_configuration_cache(sender, **kwargs):
    cache.delete('site_configuration')

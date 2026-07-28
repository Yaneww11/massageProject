import logging

from django.core.cache import cache
from django.core.files.storage import default_storage
from django.db.models.signals import post_save, pre_delete, pre_save
from django.dispatch import receiver
from django.conf import settings
from django.contrib.auth import get_user_model
from google.cloud import storage
import sentry_sdk

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


UserModel = get_user_model()


@receiver(pre_save)
def delete_old_image_on_update(sender, instance, **kwargs):
    """
    Delete old image from GCS when a new image is uploaded or when image is removed
    """
    # Get all ImageField names for the model
    image_fields = []
    for field in instance._meta.fields:
        if field.__class__.__name__ == 'ImageField':
            image_fields.append(field.name)

    if not image_fields:
        return

    for field_name in image_fields:
        try:
            new_file = getattr(instance, field_name)
            old_file_path = get_old_file_path(instance, field_name)

            # Delete old file if:
            # 1. There's a new file and an old file, and they're different
            # 2. There's no new file but there's an old file (image was removed)
            if old_file_path and (
                    (new_file and new_file.name != old_file_path) or
                    (not new_file)
            ):
                delete_file_from_gcs(old_file_path)
        except Exception as e:
            sentry_sdk.capture_exception(e, extra={
                'model': sender.__name__,
                'field_name': field_name,
                'instance_pk': getattr(instance, 'pk', 'unknown'),
                'operation': 'delete_old_image_on_update',
                'new_file': getattr(new_file, 'name', 'unknown') if 'new_file' in locals() else 'unknown',
                'old_file_path': old_file_path if 'old_file_path' in locals() else 'unknown'
            })


@receiver(pre_delete)
def delete_image_on_model_delete(sender, instance, **kwargs):
    """
    Delete image from GCS when model instance is deleted
    """
    # Get all ImageField names for the model
    image_fields = []
    for field in instance._meta.fields:
        if field.__class__.__name__ == 'ImageField':
            image_fields.append(field.name)

    if not image_fields:
        return

    for field_name in image_fields:
        try:
            file_field = getattr(instance, field_name)
            if file_field:
                delete_file_from_gcs(file_field.name)
        except Exception as e:
            sentry_sdk.capture_exception(e, extra={
                'model': sender.__name__,
                'field_name': field_name,
                'instance_pk': getattr(instance, 'pk', 'unknown'),
                'operation': 'delete_image_on_model_delete',
                'file_field_name': getattr(file_field, 'name', 'unknown') if 'file_field' in locals() else 'unknown'
            })


def delete_file_from_gcs(file_path):
    """
    Delete a file from Google Cloud Storage
    """
    if not file_path:
        return

    if not hasattr(settings, 'GS_BUCKET_NAME') or not settings.GS_BUCKET_NAME:
        return

    try:
        # Initialize GCS client
        client = storage.Client(credentials=settings.GS_CREDENTIALS, project=settings.GS_CREDENTIALS.project_id)
        bucket = client.bucket(settings.GS_BUCKET_NAME)

        # Remove the media URL prefix if present
        if file_path.startswith(settings.MEDIA_URL):
            file_path = file_path[len(settings.MEDIA_URL):]

        # Remove leading slash if present
        if file_path.startswith('/'):
            file_path = file_path[1:]

        # Skip if file_path is empty after cleaning
        if not file_path.strip():
            return

        # Get the blob and delete it
        blob = bucket.blob(file_path)
        if blob.exists():
            blob.delete()
        else:
            pass

    except Exception as e:
        sentry_sdk.capture_exception(e, extra={
            'file_path': file_path,
            'operation': 'delete_file_from_gcs',
            'bucket_name': getattr(settings, 'GS_BUCKET_NAME', 'unknown')
        })


def get_old_file_path(instance, field_name):
    """
    Get the old file path for a model instance field
    """
    try:
        if instance.pk:
            old_instance = instance.__class__.objects.get(pk=instance.pk)
            old_file = getattr(old_instance, field_name)
            if old_file:
                return old_file.name
    except instance.__class__.DoesNotExist:
        pass
    except Exception as e:
        sentry_sdk.capture_exception(e, extra={
            'model': instance.__class__.__name__,
            'field_name': field_name,
            'instance_pk': instance.pk,
            'operation': 'get_old_file_path'
        })
    return None


@receiver(post_save, sender=SiteConfiguration)
def invalidate_site_configuration_cache(sender, **kwargs):
    cache.delete('site_configuration')


@receiver(post_save, sender=HomePage)
def invalidate_homepage_cache(sender, **kwargs):
    cache.delete(HOMEPAGE_CACHE_KEY)


@receiver(post_save, sender=BusinessInfo)
def invalidate_business_info_cache(sender, **kwargs):
    cache.delete(BUSINESS_INFO_CACHE_KEY)

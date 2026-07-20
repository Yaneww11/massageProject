from modeltranslation.translator import register, TranslationOptions
from massageProject.main_app.models import (
    Service, Specialist, HomePage, BusinessInfo, BusinessWorkingHours, Image, ServiceGroup,
    Gallery, GalleryAlbum, AlbumPhoto, SiteConfiguration,
)


@register(Service)
class ServiceTranslationOptions(TranslationOptions):
    fields = ('name', 'description', 'short_description')


@register(Specialist)
class SpecialistTranslationOptions(TranslationOptions):
    fields = ('name', 'description')


@register(HomePage)
class HomePageTranslationOptions(TranslationOptions):
    fields = ('brand_name', 'description', 'privacy_policy_content', 'footer_tagline')


@register(BusinessInfo)
class BusinessInfoTranslationOptions(TranslationOptions):
    fields = ('name', 'description', 'address')


@register(BusinessWorkingHours)
class BusinessWorkingHoursTranslationOptions(TranslationOptions):
    fields = ('day_label', 'hours')


@register(Image)
class ImageTranslationOptions(TranslationOptions):
    fields = ('alt_text',)


@register(ServiceGroup)
class ServiceGroupTranslationOptions(TranslationOptions):
    fields = ('name',)


@register(Gallery)
class GalleryTranslationOptions(TranslationOptions):
    fields = ('title', 'short_description')


@register(GalleryAlbum)
class GalleryAlbumTranslationOptions(TranslationOptions):
    fields = ('title', 'description')


@register(AlbumPhoto)
class AlbumPhotoTranslationOptions(TranslationOptions):
    fields = ('alt_text',)


@register(SiteConfiguration)
class SiteConfigurationTranslationOptions(TranslationOptions):
    fields = ('service_singular', 'service_plural', 'specialist_singular', 'specialist_plural')

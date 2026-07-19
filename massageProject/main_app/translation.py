from modeltranslation.translator import register, TranslationOptions
from massageProject.main_app.models import (
    Service, Masseur, HomePage, MessageStudio, StudioWorkingHours, Image, ServiceGroup,
    Gallery, GalleryAlbum, AlbumPhoto,
)


@register(Service)
class ServiceTranslationOptions(TranslationOptions):
    fields = ('name', 'description', 'short_description')


@register(Masseur)
class MasseurTranslationOptions(TranslationOptions):
    fields = ('name', 'description')


@register(HomePage)
class HomePageTranslationOptions(TranslationOptions):
    fields = ('brand_name', 'description', 'privacy_policy_content', 'footer_tagline')


@register(MessageStudio)
class MessageStudioTranslationOptions(TranslationOptions):
    fields = ('name', 'description', 'address')


@register(StudioWorkingHours)
class StudioWorkingHoursTranslationOptions(TranslationOptions):
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

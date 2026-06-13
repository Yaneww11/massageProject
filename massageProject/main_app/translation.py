from modeltranslation.translator import register, TranslationOptions
from massageProject.main_app.models import (
    Massage, Masseur, HomePage, MessageStudio, StudioWorkingHours, Image
)


@register(Massage)
class MassageTranslationOptions(TranslationOptions):
    fields = ('name', 'description', 'short_description')


@register(Masseur)
class MasseurTranslationOptions(TranslationOptions):
    fields = ('name', 'description')


@register(HomePage)
class HomePageTranslationOptions(TranslationOptions):
    fields = ('brand_name', 'description', 'privacy_policy_content')


@register(MessageStudio)
class MessageStudioTranslationOptions(TranslationOptions):
    fields = ('name', 'description', 'address')


@register(StudioWorkingHours)
class StudioWorkingHoursTranslationOptions(TranslationOptions):
    fields = ('day_label', 'hours')


@register(Image)
class ImageTranslationOptions(TranslationOptions):
    fields = ('alt_text',)

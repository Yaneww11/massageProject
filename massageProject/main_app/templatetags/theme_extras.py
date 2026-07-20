from django import template
from django.utils.safestring import mark_safe

from massageProject.main_app.theme import FONT_PAIRS, STYLE_PRESETS

register = template.Library()


@register.filter
def font_pair_info(pair_key):
    pair = FONT_PAIRS.get(pair_key, FONT_PAIRS['playfair_montserrat'])
    return {k: mark_safe(v) if isinstance(v, str) else v for k, v in pair.items()}


@register.filter
def style_preset_vars(preset_key):
    preset = STYLE_PRESETS.get(preset_key, STYLE_PRESETS['soft'])
    return {k: mark_safe(v) if isinstance(v, str) else v for k, v in preset.items()}

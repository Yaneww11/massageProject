from django import template

register = template.Library()

EMPTY_MARKER = '[empty]'


@register.filter
def hide_if_marker(value):
    """Render as an empty string when the translated value is the EMPTY_MARKER sentinel."""
    if value is not None and str(value).strip() == EMPTY_MARKER:
        return ''
    return value

from django import template

register = template.Library()


@register.filter
def initials(name):
    if not name:
        return ''
    parts = name.split()
    return ''.join(p[0].upper() for p in parts[:2] if p)


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

from django import template


register = template.Library()


@register.filter(name='translate_messages')
def translate_messages(message):
    return message

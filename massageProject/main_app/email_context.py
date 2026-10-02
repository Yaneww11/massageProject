"""Shared context and message construction for transactional email.

Email is rendered outside the request/response cycle, so neither the
context processors nor the request's active language apply: both have to be
supplied explicitly here.
"""
from contextlib import contextmanager
from email.utils import formataddr
from urllib.parse import urljoin

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import translation
from django.utils.translation import gettext_lazy as _


@contextmanager
def site_language():
    """Render in the site's own language, whatever the caller was doing.

    Not django.utils.translation.override: when no language is active (a
    management command, a shell, a test) its __exit__ calls deactivate_all(),
    which leaves translations switched off for everything that runs after.
    """
    previous = translation.get_language()
    translation.activate(settings.LANGUAGE_CODE)
    try:
        yield
    finally:
        translation.activate(previous or settings.LANGUAGE_CODE)


def absolute_url(path):
    """Build an inbox-safe absolute URL from a site-relative path."""
    return urljoin(f'{settings.SITE_URL}/', path.lstrip('/'))


def email_url(viewname, *args):
    """Absolute URL for an emailed link, in the site's own language.

    Reversing has to happen under the override: the project's URLs live in
    i18n_patterns, so an unwrapped reverse() would emit whichever language
    prefix the triggering visitor happened to be browsing in.
    """
    with site_language():
        return absolute_url(reverse(viewname, args=args))


def email_branding():
    """Brand, theme and contact details every email template needs."""
    from massageProject.main_app.models import BusinessInfo, HomePage, SiteConfiguration

    homepage = HomePage.get_solo()
    site_config = SiteConfiguration.get_solo()

    logo_url = None
    if site_config and site_config.email_logo:
        logo_url = absolute_url(site_config.email_logo.url)

    return {
        'brand_name': homepage.brand_name_plain if homepage else _('Relax & Health'),
        'site_config': site_config,
        'business_info': BusinessInfo.objects.first(),
        'email_logo_url': logo_url,
    }


def build_email(template_prefix, to_email, context):
    """Render subject, plain-text and HTML bodies under the site language.

    Rendering and URL reversing both happen inside the override so the
    subject, both bodies and every link agree on one language -- otherwise
    they follow whichever visitor's request happened to trigger the send.
    """
    with site_language():
        # brand_name comes from a modeltranslation field, so the branding
        # lookup belongs inside the override too -- outside it the From header
        # and footers would follow the visitor's language while the bodies
        # follow the site's.
        context = {**email_branding(), **context}
        subject = render_to_string(f'emails/{template_prefix}_subject.txt', context).strip()
        text_body = render_to_string(f'emails/{template_prefix}.txt', context)
        html_body = render_to_string(f'emails/{template_prefix}.html', context)

    site_config = context['site_config']
    reply_to = [site_config.email_reply_to] if site_config and site_config.email_reply_to else None

    message = EmailMultiAlternatives(
        subject,
        text_body,
        formataddr((str(context['brand_name']), settings.DEFAULT_FROM_EMAIL)),
        [to_email],
        reply_to=reply_to,
    )
    message.attach_alternative(html_body, 'text/html')
    return message

from email.utils import formataddr

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext_lazy as _


def _brand_name():
    from massageProject.main_app.models import HomePage

    homepage = HomePage.get_solo()
    return homepage.brand_name if homepage else _('Relax & Health')


def _send_reservation_email(template_prefix, to_email, context):
    context = {**context, 'brand_name': _brand_name()}
    subject = render_to_string(f'emails/{template_prefix}_subject.txt', context).strip()
    text_body = render_to_string(f'emails/{template_prefix}.txt', context)
    html_body = render_to_string(f'emails/{template_prefix}.html', context)

    from_email = formataddr((str(context['brand_name']), settings.DEFAULT_FROM_EMAIL))
    message = EmailMultiAlternatives(subject, text_body, from_email, [to_email])
    message.attach_alternative(html_body, 'text/html')
    message.send()


def send_gallery_ready_email(request, reservation):
    """Notifies the client their Proofing Gallery is ready to review."""
    client_name = reservation.user.get_full_name() or str(reservation.user.phone_number)
    review_url = request.build_absolute_uri(reverse('photo_proofing'))
    _send_reservation_email('gallery_ready_email', reservation.user.email, {
        'client_name': client_name,
        'review_url': review_url,
    })


def send_marks_finalized_email(request, reservation):
    """Notifies the specialist (by their own contact email, not a login-linked
    one, so it reaches specialists without an account) that the client has
    finalized their marked photos."""
    client_name = reservation.user.get_full_name() or str(reservation.user.phone_number)
    marked_photos_url = request.build_absolute_uri(
        reverse('marked_photos', args=[reservation.pk])
    )
    _send_reservation_email('marks_finalized_email', reservation.specialist.email, {
        'client_name': client_name,
        'reservation': reservation,
        'marked_photos_url': marked_photos_url,
    })


def send_final_delivery_email(request, reservation):
    """Notifies the client their Final Gallery is ready, with a secure
    download link (not an attachment)."""
    client_name = reservation.user.get_full_name() or str(reservation.user.phone_number)
    download_url = request.build_absolute_uri(
        reverse('final_gallery_download', args=[reservation.pk])
    )
    _send_reservation_email('final_delivery_email', reservation.user.email, {
        'client_name': client_name,
        'download_url': download_url,
    })

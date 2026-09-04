import logging
from email.utils import formataddr

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


def _brand_name():
    from massageProject.main_app.models import HomePage

    homepage = HomePage.get_solo()
    return homepage.brand_name if homepage else _('Relax & Health')


def _send_reservation_email(template_prefix, to_email, context):
    """Best-effort send: a transient mail-provider failure is logged rather
    than raised, so it can't 500 the request after other work (e.g. a
    gallery upload) already committed. Returns whether the send succeeded."""
    context = {**context, 'brand_name': _brand_name()}
    subject = render_to_string(f'emails/{template_prefix}_subject.txt', context).strip()
    text_body = render_to_string(f'emails/{template_prefix}.txt', context)
    html_body = render_to_string(f'emails/{template_prefix}.html', context)

    from_email = formataddr((str(context['brand_name']), settings.DEFAULT_FROM_EMAIL))
    message = EmailMultiAlternatives(subject, text_body, from_email, [to_email])
    message.attach_alternative(html_body, 'text/html')
    try:
        message.send()
    except Exception:
        logger.exception('Failed to send %s email to %s', template_prefix, to_email)
        return False
    return True


def send_gallery_ready_email(request, reservation):
    """Notifies the client their Proofing Gallery is ready to review."""
    client_name = reservation.user.get_full_name() or str(reservation.user.phone_number)
    review_url = request.build_absolute_uri(reverse('photo_proofing'))
    return _send_reservation_email('gallery_ready_email', reservation.user.email, {
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
    return _send_reservation_email('marks_finalized_email', reservation.specialist.email, {
        'client_name': client_name,
        'reservation': reservation,
        'marked_photos_url': marked_photos_url,
    })


def send_final_delivery_email(request, reservation):
    """Notifies the client their Final Gallery is ready, with a secure
    download link (not an attachment). Stamps finals_delivered_at the moment
    the email sends successfully — no separate manual "mark as delivered" step."""
    client_name = reservation.user.get_full_name() or str(reservation.user.phone_number)
    download_url = request.build_absolute_uri(
        reverse('final_gallery_download', args=[reservation.pk])
    )
    sent = _send_reservation_email('final_delivery_email', reservation.user.email, {
        'client_name': client_name,
        'download_url': download_url,
    })
    if sent:
        reservation.finals_delivered_at = timezone.now()
        reservation.save(update_fields=['finals_delivered_at'])
    return sent

import logging

from django.utils import timezone

from massageProject.main_app.email_context import build_email, email_url

logger = logging.getLogger(__name__)


def _send_reservation_email(template_prefix, to_email, context):
    """Best-effort send: a transient mail-provider failure is logged rather
    than raised, so it can't 500 the request after other work (e.g. a
    gallery upload) already committed. Returns whether the send succeeded."""
    try:
        build_email(template_prefix, to_email, context).send()
    except Exception:
        logger.exception('Failed to send %s email to %s', template_prefix, to_email)
        return False
    return True


def _client_name(reservation):
    return reservation.user.get_full_name() or reservation.user.phone_number or reservation.user.email


def send_gallery_ready_email(reservation):
    """Notifies the client their Proofing Gallery is ready to review."""
    return _send_reservation_email('gallery_ready_email', reservation.user.email, {
        'client_name': _client_name(reservation),
        'review_url': email_url('photo_proofing'),
    })


def send_marks_finalized_email(reservation):
    """Notifies the specialist (by their own contact email, not a login-linked
    one, so it reaches specialists without an account) that the client has
    finalized their marked photos."""
    return _send_reservation_email('marks_finalized_email', reservation.specialist.email, {
        'client_name': _client_name(reservation),
        'reservation': reservation,
        'marked_photos_url': email_url('marked_photos', reservation.pk),
    })


def send_final_delivery_email(reservation):
    """Notifies the client their Final Gallery is ready, with a secure
    download link (not an attachment). Stamps finals_delivered_at the moment
    the email sends successfully — no separate manual "mark as delivered" step."""
    sent = _send_reservation_email('final_delivery_email', reservation.user.email, {
        'client_name': _client_name(reservation),
        'download_url': email_url('final_gallery_download', reservation.pk),
    })
    if sent:
        reservation.finals_delivered_at = timezone.now()
        reservation.save(update_fields=['finals_delivered_at'])
    return sent

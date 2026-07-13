from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import gettext_lazy as _

from massageProject.accounts.tokens import email_verification_token_generator


def send_verification_email(request, user):
    from massageProject.main_app.models import HomePage

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token_generator.make_token(user)
    verify_url = request.build_absolute_uri(
        reverse('verify_email', kwargs={'uidb64': uid, 'token': token})
    )

    homepage = HomePage.get_solo()
    logo_url = None
    if homepage and homepage.logo:
        logo_url = request.build_absolute_uri(homepage.logo.url)

    context = {
        'user': user,
        'verify_url': verify_url,
        'brand_name': homepage.brand_name if homepage else _('Relax & Health'),
        'logo_url': logo_url,
    }
    subject = render_to_string('emails/verification_email_subject.txt', context).strip()
    text_body = render_to_string('emails/verification_email.txt', context)
    html_body = render_to_string('emails/verification_email.html', context)

    email = EmailMultiAlternatives(subject, text_body, settings.DEFAULT_FROM_EMAIL, [user.email])
    email.attach_alternative(html_body, 'text/html')
    email.send()


def send_otp_email(request, email, code):
    from massageProject.main_app.models import HomePage

    homepage = HomePage.get_solo()
    logo_url = None
    if homepage and homepage.logo:
        logo_url = request.build_absolute_uri(homepage.logo.url)

    context = {
        'code': code,
        'brand_name': homepage.brand_name if homepage else _('Relax & Health'),
        'logo_url': logo_url,
    }
    subject = render_to_string('emails/otp_email_subject.txt', context).strip()
    text_body = render_to_string('emails/otp_email.txt', context)
    html_body = render_to_string('emails/otp_email.html', context)

    message = EmailMultiAlternatives(subject, text_body, settings.DEFAULT_FROM_EMAIL, [email])
    message.attach_alternative(html_body, 'text/html')
    message.send()

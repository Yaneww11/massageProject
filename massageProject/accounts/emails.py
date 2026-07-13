from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _


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

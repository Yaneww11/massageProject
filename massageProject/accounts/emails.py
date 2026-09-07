from email.utils import formataddr

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _


def send_otp_email(email, code):
    from massageProject.main_app.models import HomePage

    homepage = HomePage.get_solo()
    brand_name = homepage.brand_name_plain if homepage else _('Relax & Health')

    context = {
        'code': code,
        'brand_name': brand_name,
    }
    subject = render_to_string('emails/otp_email_subject.txt', context).strip()
    text_body = render_to_string('emails/otp_email.txt', context)
    html_body = render_to_string('emails/otp_email.html', context)

    from_email = formataddr((str(brand_name), settings.DEFAULT_FROM_EMAIL))
    message = EmailMultiAlternatives(subject, text_body, from_email, [email])
    message.attach_alternative(html_body, 'text/html')
    message.send()

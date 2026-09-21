from django.conf import settings
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.views import PasswordResetView
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.views.generic import TemplateView

from massageProject.main_app.email_context import email_branding, site_language


class AuthEntryView(TemplateView):
    """
    Fallback destination for the 'login' URL name -- Django's default
    LOGIN_URL. LoginRequiredMixin/@login_required (ProfilePage,
    edit_reservation, delete_reservation) redirect anonymous users here.
    Instead of a full login page, this renders the site shell and
    auto-opens the shared auth modal (partials/auth_modal.html), passing
    along ?next= so the modal knows where to send the user afterward.
    """
    template_name = 'registration/auth_entry.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['next'] = self.request.GET.get('next', '')
        return context


class BrandedPasswordResetForm(PasswordResetForm):
    """Django's PasswordResetForm builds its own message with no reply_to
    hook, so the site's configured reply address can only be applied by
    rebuilding the message here."""

    def send_mail(self, subject_template_name, email_template_name, context,
                  from_email, to_email, html_email_template_name=None):
        subject = ''.join(render_to_string(subject_template_name, context).splitlines())
        body = render_to_string(email_template_name, context)

        site_config = context.get('site_config')
        reply_to = [site_config.email_reply_to] if site_config and site_config.email_reply_to else None

        message = EmailMultiAlternatives(subject, body, from_email, [to_email], reply_to=reply_to)
        if html_email_template_name is not None:
            message.attach_alternative(render_to_string(html_email_template_name, context), 'text/html')
        message.send()


class BrandedPasswordResetView(PasswordResetView):
    template_name = 'registration/password_reset_form.html'
    email_template_name = 'emails/password_reset_email.txt'
    html_email_template_name = 'emails/password_reset_email.html'
    subject_template_name = 'emails/password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')

    form_class = BrandedPasswordResetForm

    @property
    def from_email(self):
        from email.utils import formataddr

        return formataddr((str(email_branding()['brand_name']), settings.DEFAULT_FROM_EMAIL))

    @property
    def extra_email_context(self):
        return email_branding()

    def form_valid(self, form):
        """Django builds and sends this email inside form.save(), so the
        language override has to wrap the whole call -- otherwise the subject,
        bodies and reset link follow the browsing visitor's language rather
        than the site's."""
        with site_language():
            return super().form_valid(form)

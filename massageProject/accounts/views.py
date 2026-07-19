from django.contrib.auth.views import PasswordResetView
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView


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


class BrandedPasswordResetView(PasswordResetView):
    template_name = 'registration/password_reset_form.html'
    email_template_name = 'emails/password_reset_email.txt'
    html_email_template_name = 'emails/password_reset_email.html'
    subject_template_name = 'emails/password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')

    @property
    def extra_email_context(self):
        from massageProject.main_app.models import HomePage, BusinessInfo

        homepage = HomePage.get_solo()
        business_info = BusinessInfo.objects.first()
        logo_url = None
        if homepage and homepage.logo:
            logo_url = self.request.build_absolute_uri(homepage.logo.url)

        return {
            'brand_name': homepage.brand_name if homepage else _('Relax & Health'),
            'business_info': business_info,
            'logo_url': logo_url,
        }

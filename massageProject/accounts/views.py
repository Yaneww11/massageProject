from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.views import PasswordResetView
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import CreateView, FormView

from massageProject.accounts.emails import send_verification_email
from massageProject.accounts.forms import CustomUserForm, ResendVerificationForm
from massageProject.accounts.tokens import email_verification_token_generator

User = get_user_model()


class UserRegisterView(CreateView):
    template_name = 'registration/register.html'
    form_class = CustomUserForm
    success_url = reverse_lazy('verification_sent')

    def form_valid(self, form):
        user = form.save(commit=False)
        user.is_active = False
        user.save()
        send_verification_email(self.request, user)
        return redirect(self.success_url)


class VerifyEmailView(View):
    def get(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None

        if user is not None and email_verification_token_generator.check_token(user, token):
            user.is_active = True
            user.save(update_fields=['is_active'])
            login(request, user, backend='massageProject.accounts.backends.VerificationAwareBackend')
            messages.success(request, _("Имейлът Ви е потвърден успешно. Добре дошли!"))
            return redirect('reservation_page')

        messages.error(request, _("Този линк за потвърждение е невалиден или е изтекъл."))
        return redirect('resend_verification')


class ResendVerificationView(FormView):
    template_name = 'registration/resend_verification.html'
    form_class = ResendVerificationForm
    success_url = reverse_lazy('verification_sent')

    def form_valid(self, form):
        email = form.cleaned_data['email']
        try:
            user = User.objects.get(email__iexact=email, is_active=False)
            send_verification_email(self.request, user)
        except User.DoesNotExist:
            pass
        return super().form_valid(form)


class BrandedPasswordResetView(PasswordResetView):
    template_name = 'registration/password_reset_form.html'
    email_template_name = 'emails/password_reset_email.txt'
    html_email_template_name = 'emails/password_reset_email.html'
    subject_template_name = 'emails/password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')

    @property
    def extra_email_context(self):
        from massageProject.main_app.models import HomePage, MessageStudio

        homepage = HomePage.get_solo()
        studio = MessageStudio.objects.first()
        logo_url = None
        if homepage and homepage.logo:
            logo_url = self.request.build_absolute_uri(homepage.logo.url)

        return {
            'brand_name': homepage.brand_name if homepage else _('Relax & Health'),
            'studio': studio,
            'logo_url': logo_url,
        }

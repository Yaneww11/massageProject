from django.urls import path
from django.contrib.auth.views import (
    LoginView, LogoutView, PasswordResetDoneView,
    PasswordResetConfirmView, PasswordResetCompleteView,
)
from django.urls import reverse_lazy
from django.views.generic import TemplateView

from massageProject.accounts.views import (
    UserRegisterView, VerifyEmailView, ResendVerificationView, BrandedPasswordResetView,
)
from massageProject.accounts.forms import CustomAuthenticationForm
from massageProject.accounts.booking_auth_views import check_email, send_code, verify_code, register_via_modal

urlpatterns = [
    path('register/', UserRegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(authentication_form=CustomAuthenticationForm), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),

    path('auth-modal/check-email/', check_email, name='auth_check_email'),
    path('auth-modal/send-code/', send_code, name='auth_send_code'),
    path('auth-modal/verify-code/', verify_code, name='auth_verify_code'),
    path('auth-modal/register/', register_via_modal, name='auth_register'),

    path('verification-sent/', TemplateView.as_view(template_name='registration/verification_sent.html'), name='verification_sent'),
    path('verify/<uidb64>/<token>/', VerifyEmailView.as_view(), name='verify_email'),
    path('resend-verification/', ResendVerificationView.as_view(), name='resend_verification'),

    path('password-reset/', BrandedPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html'
    ), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html',
        success_url=reverse_lazy('password_reset_complete'),
    ), name='password_reset_confirm'),
    path('reset/done/', PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html'
    ), name='password_reset_complete'),
]

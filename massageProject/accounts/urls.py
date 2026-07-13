from django.urls import path, reverse_lazy
from django.contrib.auth.views import (
    LogoutView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView,
)

from massageProject.accounts.views import AuthEntryView, BrandedPasswordResetView
from massageProject.accounts.booking_auth_views import (
    check_email, send_code, verify_code, register_via_modal, login_password,
)

urlpatterns = [
    path('login/', AuthEntryView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),

    path('auth-modal/check-email/', check_email, name='auth_check_email'),
    path('auth-modal/send-code/', send_code, name='auth_send_code'),
    path('auth-modal/verify-code/', verify_code, name='auth_verify_code'),
    path('auth-modal/register/', register_via_modal, name='auth_register'),
    path('auth-modal/login-password/', login_password, name='auth_login_password'),

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

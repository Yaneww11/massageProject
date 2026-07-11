from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from django.views.generic import TemplateView

from massageProject.accounts.views import UserRegisterView, VerifyEmailView
from massageProject.accounts.forms import CustomAuthenticationForm

urlpatterns = [
    path('register/', UserRegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(authentication_form=CustomAuthenticationForm), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),

    path('verification-sent/', TemplateView.as_view(template_name='registration/verification_sent.html'), name='verification_sent'),
    path('verify/<uidb64>/<token>/', VerifyEmailView.as_view(), name='verify_email'),
]

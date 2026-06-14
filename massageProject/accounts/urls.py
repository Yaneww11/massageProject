from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from massageProject.accounts.views import UserRegisterView
from massageProject.accounts.forms import CustomAuthenticationForm

urlpatterns = [
    path('register/', UserRegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(authentication_form=CustomAuthenticationForm), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
]
from django.urls import path, include

from massageProject.main_app.views import Index, MassagesDashboard, ReservationPage, AboutPage, ProfilePage, \
    MassageDetail

urlpatterns = [
    path('', Index.as_view(), name='index'),
    path('massages/', MassagesDashboard.as_view(), name='massages_dashboard'),
    path('reserve/', ReservationPage.as_view(), name='reservation_page'),
    path('reserve/<int:pk>/', ReservationPage.as_view(), name='reservation_page'),
    path('about/', AboutPage.as_view(), name='about_page'),
    path('profile/', ProfilePage.as_view(), name='profile_page'),
    path('massage/<int:pk>/', MassageDetail.as_view(), name='massage_detail'),
]
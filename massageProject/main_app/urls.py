from django.urls import path, include

from massageProject.main_app.views import Index, MassagesDashboard, ReservationPage, AboutPage, ProfilePage, \
    MassageDetail, edit_reservation, delete_reservation, PrivacyPolicyView, check_availability

urlpatterns = [
    path('', Index.as_view(), name='index'),
    path('privacy-policy/', PrivacyPolicyView.as_view(), name='privacy_policy'),
    path('massages/', MassagesDashboard.as_view(), name='massages_dashboard'),
    path('reserve/', ReservationPage.as_view(), name='reservation_page'),
    path('check-availability/', check_availability, name='check_availability'),
    path('about/', AboutPage.as_view(), name='about_page'),
    path('profile/', ProfilePage.as_view(), name='profile_page'),
    path('massage/<int:pk>/', MassageDetail.as_view(), name='massage_detail'),

    path('<int:pk>/', include([
        path('create_reserve/', ReservationPage.as_view(), name='reservation_page'),
        path('edit_reserve/', edit_reservation, name='edit_reservation'),
        path('delete_reserve/', delete_reservation, name='delete_reservation'),
    ])),

]
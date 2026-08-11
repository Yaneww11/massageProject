from django.urls import path, include

from massageProject.main_app.views import Index, ServicesDashboard, ReservationPage, AboutPage, ProfilePage, \
    edit_reservation, delete_reservation, PrivacyPolicyView, check_availability, AllCommentsView, \
    submit_comment, GalleryView, GalleryAlbumView, PhotoProofingGallery, mark_photo, toggle_photo_label, \
    save_photo_comment, finalize_photo_proofing, serve_proof_image, download_reservation_ics

urlpatterns = [
    path('', Index.as_view(), name='index'),
    path('privacy-policy/', PrivacyPolicyView.as_view(), name='privacy_policy'),
    path('services/', ServicesDashboard.as_view(), name='services_dashboard'),
    path('reserve/', ReservationPage.as_view(), name='reservation_page'),
    path('check-availability/', check_availability, name='check_availability'),
    path('about/', AboutPage.as_view(), name='about_page'),
    path('comments/', AllCommentsView.as_view(), name='all_comments'),
    path('submit-comment/', submit_comment, name='submit_comment'),
    path('profile/', ProfilePage.as_view(), name='profile_page'),
    path('profile/reservations/<int:reservation_id>/calendar/', download_reservation_ics, name='reservation_calendar_ics'),
    path('profile/photos/', PhotoProofingGallery.as_view(), name='photo_proofing'),
    path('profile/photos/<int:image_id>/mark/', mark_photo, name='photo_proofing_mark'),
    path('profile/photos/<int:image_id>/label/<int:label_id>/', toggle_photo_label, name='photo_proofing_label'),
    path('profile/photos/<int:image_id>/comment/', save_photo_comment, name='photo_proofing_comment'),
    path('profile/photos/finalize/', finalize_photo_proofing, name='photo_proofing_finalize'),
    path('profile/photos/img/<str:token>/', serve_proof_image, name='photo_proofing_image'),
    path('gallery/', GalleryView.as_view(), name='gallery'),
    path('gallery/<slug:slug>/', GalleryAlbumView.as_view(), name='gallery_album'),

    path('<int:pk>/', include([
        path('create_reserve/', ReservationPage.as_view(), name='reservation_page'),
        path('edit_reserve/', edit_reservation, name='edit_reservation'),
        path('delete_reserve/', delete_reservation, name='delete_reservation'),
    ])),

]
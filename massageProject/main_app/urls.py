from django.urls import path, include

from massageProject.main_app.views import Index, ServicesDashboard, ReservationPage, AboutPage, ProfilePage, \
    edit_reservation, delete_reservation, PrivacyPolicyView, check_availability, AllCommentsView, \
    submit_comment, GalleryView, GalleryAlbumView, PhotoProofingGallery, mark_photo, toggle_photo_label, \
    save_photo_comment, finalize_photo_proofing, serve_proof_image, download_reservation_ics, \
    ProofingGalleryUploadView, MarkedPhotosView, serve_marked_photo_image, download_marked_photo, \
    download_marked_photos_zip, FinalGalleryUploadView, serve_final_gallery_image, download_final_gallery

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
    path('profile/gallery-upload/', ProofingGalleryUploadView.as_view(), name='proofing_gallery_upload'),
    path('profile/reservations/<int:reservation_id>/marked-photos/', MarkedPhotosView.as_view(), name='marked_photos'),
    path('profile/reservations/<int:reservation_id>/marked-photos/zip/', download_marked_photos_zip, name='marked_photos_zip'),
    path('profile/reservations/<int:reservation_id>/marked-photos/<int:image_id>/', serve_marked_photo_image, name='marked_photo_image'),
    path('profile/reservations/<int:reservation_id>/marked-photos/<int:image_id>/download/', download_marked_photo, name='marked_photo_download'),
    path('profile/final-gallery-upload/', FinalGalleryUploadView.as_view(), name='final_gallery_upload'),
    path('profile/reservations/<int:reservation_id>/final-gallery/', download_final_gallery, name='final_gallery_download'),
    path('profile/reservations/<int:reservation_id>/final-gallery/<int:image_id>/', serve_final_gallery_image, name='final_gallery_image'),
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
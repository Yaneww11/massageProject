from datetime import time as time_cls, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from massageProject.accounts.models import CustomUser
from massageProject.main_app.models import (
    Gallery, Image, Reservation, Service, Specialist, WorkingHours,
)


class FinalGalleryModelsBase(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            phone_number='0888222221', email='client-final@example.com', password='pass12345',
        )
        self.service = Service.objects.create(
            name='Photoshoot', description='d', price=150, duration_in_minutes=60, short_description='s',
        )
        self.specialist = Specialist.objects.create(
            name='Nadia', description='d', phone_number='0888222222', email='nadia@example.com',
        )
        candidate = timezone.localdate() + timedelta(days=7)
        while candidate.weekday() != 0:
            candidate += timedelta(days=1)
        self.future_monday = candidate
        WorkingHours.objects.create(
            specialist=self.specialist, day_of_week=0, start_time=time_cls(9, 0), end_time=time_cls(17, 0),
        )
        self.proofing_gallery = Gallery.objects.create(gallery_type=Gallery.TYPE_PROOFING)
        self.reservation = Reservation.objects.create(
            user=self.user, service=self.service, specialist=self.specialist,
            date=self.future_monday, time=time_cls(10, 0), gallery=self.proofing_gallery,
        )

    def _make_final_gallery(self):
        return Gallery.objects.create(gallery_type=Gallery.TYPE_FINAL)


class GalleryTypeChoicesTest(TestCase):
    def test_proofing_type_replaces_reservation_type(self):
        self.assertIn(Gallery.TYPE_PROOFING, dict(Gallery.TYPE_CHOICES))
        self.assertEqual(Gallery.TYPE_PROOFING, 'proofing')

    def test_final_type_exists(self):
        self.assertIn(Gallery.TYPE_FINAL, dict(Gallery.TYPE_CHOICES))
        self.assertEqual(Gallery.TYPE_FINAL, 'final')


class ReservationFinalGalleryOrderingInvariantsTest(FinalGalleryModelsBase):
    def test_attaching_final_gallery_before_finalizing_is_rejected(self):
        self.reservation.final_gallery = self._make_final_gallery()
        with self.assertRaises(ValidationError):
            self.reservation.full_clean()

    def test_attaching_final_gallery_after_finalizing_is_allowed(self):
        self.reservation.finalize_proofing()
        final_gallery = self._make_final_gallery()
        self.reservation.final_gallery = final_gallery
        self.reservation.save()
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.final_gallery_id, final_gallery.pk)

    def test_recording_delivery_before_final_gallery_is_rejected(self):
        self.reservation.finalize_proofing()
        self.reservation.finals_delivered_at = timezone.now()
        with self.assertRaises(ValidationError):
            self.reservation.full_clean()

    def test_recording_delivery_after_final_gallery_is_allowed(self):
        self.reservation.finalize_proofing()
        self.reservation.final_gallery = self._make_final_gallery()
        self.reservation.save()
        self.reservation.finals_delivered_at = timezone.now()
        self.reservation.save()
        self.reservation.refresh_from_db()
        self.assertIsNotNone(self.reservation.finals_delivered_at)

    def test_unlock_proofing_after_final_gallery_and_delivery_does_not_raise(self):
        self.reservation.finalize_proofing()
        self.reservation.final_gallery = self._make_final_gallery()
        self.reservation.save()
        self.reservation.finals_delivered_at = timezone.now()
        self.reservation.save()
        # Regression: unlock_proofing() clears proofing_finalized_at without
        # touching final_gallery/finals_delivered_at — it must not retroactively
        # fail the "final_gallery requires finalized proofing" invariant on an
        # already-delivered reservation (story 28).
        self.reservation.unlock_proofing()
        self.reservation.refresh_from_db()
        self.assertFalse(self.reservation.is_proofing_finalized)
        self.assertIsNotNone(self.reservation.final_gallery_id)
        self.assertIsNotNone(self.reservation.finals_delivered_at)

    def test_status_change_after_finals_delivered_does_not_raise(self):
        self.reservation.finalize_proofing()
        self.reservation.final_gallery = self._make_final_gallery()
        self.reservation.save()
        self.reservation.finals_delivered_at = timezone.now()
        self.reservation.save()
        self.reservation.change_status(Reservation.STATUS_NOSHOW, user=self.user)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, Reservation.STATUS_NOSHOW)
        self.assertIsNotNone(self.reservation.final_gallery_id)
        self.assertIsNotNone(self.reservation.finals_delivered_at)

    def test_freshly_constructed_reservation_with_final_gallery_but_not_finalized_is_rejected(self):
        reservation = Reservation(
            user=self.user, service=self.service, specialist=self.specialist,
            date=self.future_monday, time=time_cls(11, 0),
            final_gallery=self._make_final_gallery(),
        )
        with self.assertRaises(ValidationError):
            reservation.full_clean()


class ImageFinalGalleryValidationSkipTest(FinalGalleryModelsBase):
    def test_final_gallery_image_skips_minimum_dimension_check(self):
        final_gallery = self._make_final_gallery()
        image = Image(gallery=final_gallery, order=0, alt_text='Edited', image='gallery/tiny-final.jpg')
        # No actual pixel data is opened because clean() returns before the
        # PIL.Image.open() branch for gallery_type='final'.
        image.full_clean()

    def test_proofing_gallery_image_still_enforces_minimum_dimension_check(self):
        from io import BytesIO
        from PIL import Image as PILImage
        from django.core.files.uploadedfile import SimpleUploadedFile

        buffer = BytesIO()
        PILImage.new('RGB', (300, 300), color='red').save(buffer, format='JPEG')
        buffer.seek(0)
        upload = SimpleUploadedFile('tiny.jpg', buffer.read(), content_type='image/jpeg')
        image = Image(gallery=self.proofing_gallery, order=0, image=upload)
        with self.assertRaises(ValidationError):
            image.full_clean()


class ReservationPhaseTest(FinalGalleryModelsBase):
    def test_phase_is_finals_delivered_when_final_gallery_and_delivered_at_set(self):
        self.reservation.finalize_proofing()
        self.reservation.final_gallery = self._make_final_gallery()
        self.reservation.save()
        self.reservation.finals_delivered_at = timezone.now()
        self.reservation.save()
        self.assertEqual(self.reservation.phase, Reservation.PHASE_FINALS_DELIVERED)

    def test_phase_is_finals_ready_when_final_gallery_set_without_delivery(self):
        self.reservation.finalize_proofing()
        self.reservation.final_gallery = self._make_final_gallery()
        self.reservation.save()
        self.assertEqual(self.reservation.phase, Reservation.PHASE_FINALS_READY)

    def test_phase_is_editing_when_finalized_without_final_gallery(self):
        self.reservation.finalize_proofing()
        self.assertEqual(self.reservation.phase, Reservation.PHASE_EDITING)

    def test_phase_is_awaiting_review_when_gallery_set_and_review_flag_on(self):
        self.reservation.need_client_review = True
        self.reservation.save()
        self.assertEqual(self.reservation.phase, Reservation.PHASE_AWAITING_REVIEW)

    def test_phase_is_gallery_uploaded_when_gallery_set_but_review_flag_off(self):
        self.assertFalse(self.reservation.need_client_review)
        self.assertEqual(self.reservation.phase, Reservation.PHASE_GALLERY_UPLOADED)

    def test_phase_falls_back_to_plain_status_when_no_gallery(self):
        reservation = Reservation.objects.create(
            user=self.user, service=self.service, specialist=self.specialist,
            date=self.future_monday, time=time_cls(12, 0),
        )
        self.assertEqual(reservation.phase, Reservation.STATUS_ACTIVE)


from django.contrib import admin as django_admin
from django.test import RequestFactory

from massageProject.main_app.admin import ReservationAdmin


class ReservationAdminFinalGalleryFieldTest(FinalGalleryModelsBase):
    def setUp(self):
        super().setUp()
        self.admin_instance = ReservationAdmin(Reservation, django_admin.site)
        self.factory = RequestFactory()

    def _request(self, reservation_pk):
        request = self.factory.get(f'/admin/main_app/reservation/{reservation_pk}/change/')
        request.resolver_match = type('Match', (), {'kwargs': {'object_id': str(reservation_pk)}})()
        return request

    def test_gallery_field_excludes_galleries_already_used_as_final_gallery(self):
        self.reservation.finalize_proofing()
        final_gallery = self._make_final_gallery()
        self.reservation.final_gallery = final_gallery
        self.reservation.save()

        other_reservation = Reservation.objects.create(
            user=self.user, service=self.service, specialist=self.specialist,
            date=self.future_monday, time=time_cls(13, 0),
        )
        request = self._request(other_reservation.pk)
        db_field = Reservation._meta.get_field('gallery')
        formfield = self.admin_instance.formfield_for_foreignkey(db_field, request)
        self.assertNotIn(final_gallery, formfield.queryset)

    def test_final_gallery_field_offers_unused_galleries_and_keeps_current_one(self):
        self.reservation.finalize_proofing()
        final_gallery = self._make_final_gallery()
        self.reservation.final_gallery = final_gallery
        self.reservation.save()

        spare_gallery = self._make_final_gallery()

        request = self._request(self.reservation.pk)
        db_field = Reservation._meta.get_field('final_gallery')
        formfield = self.admin_instance.formfield_for_foreignkey(db_field, request)
        self.assertIn(final_gallery, formfield.queryset)
        self.assertIn(spare_gallery, formfield.queryset)
        self.assertNotIn(self.proofing_gallery, formfield.queryset)


class UnlockPhotoProofingActionTest(FinalGalleryModelsBase):
    def setUp(self):
        super().setUp()
        self.admin_instance = ReservationAdmin(Reservation, django_admin.site)
        self.factory = RequestFactory()

    def test_unlock_skips_reservation_whose_finals_are_already_ready_or_delivered(self):
        from massageProject.main_app.admin import unlock_photo_proofing

        self.reservation.finalize_proofing()
        self.reservation.final_gallery = self._make_final_gallery()
        self.reservation.save()

        request = self.factory.post('/admin/main_app/reservation/')
        unlock_photo_proofing(self.admin_instance, request, Reservation.objects.filter(pk=self.reservation.pk))
        self.reservation.refresh_from_db()
        self.assertTrue(self.reservation.is_proofing_finalized)

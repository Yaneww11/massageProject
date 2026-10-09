from datetime import time as time_cls, timedelta

from django.contrib import admin as django_admin
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase, override_settings
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from massageProject.accounts.models import CustomUser
from massageProject.main_app.admin import ReservationAdmin, unlock_photo_proofing
from massageProject.main_app.models import (
    Gallery, Image, Reservation, Service, Specialist, WorkingHours,
)


class FinalsStateBase(TestCase):
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


class StoredFinalsAreGoneTest(TestCase):
    def test_final_gallery_type_is_removed(self):
        self.assertNotIn('final', dict(Gallery.TYPE_CHOICES))
        self.assertFalse(hasattr(Gallery, 'TYPE_FINAL'))
        self.assertNotIn('final', Gallery.RESERVATION_SUBFOLDERS.values())
        self.assertNotIn('final', Gallery.IMAGE_CAPS)

    def test_reservation_has_no_final_gallery_field(self):
        names = {f.name for f in Reservation._meta.get_fields()}
        self.assertNotIn('final_gallery', names)

    def test_finals_ready_phase_is_removed(self):
        self.assertFalse(hasattr(Reservation, 'PHASE_FINALS_READY'))
        self.assertNotIn('finals_ready', dict(Reservation.PHOTO_PHASE_CHOICES))


class FinalsDeliveredInvariantTest(FinalsStateBase):
    def test_delivery_before_proofing_finalized_is_rejected(self):
        self.reservation.finals_delivered_at = timezone.now()
        with self.assertRaises(ValidationError) as ctx:
            self.reservation.full_clean()
        self.assertIn('finals_delivered_at', ctx.exception.message_dict)

    def test_delivery_after_proofing_finalized_is_allowed(self):
        self.reservation.finalize_proofing()
        self.reservation.finals_delivered_at = timezone.now()
        self.reservation.save()
        self.reservation.refresh_from_db()
        self.assertIsNotNone(self.reservation.finals_delivered_at)

    def test_clearing_delivery_is_allowed(self):
        self.reservation.finalize_proofing()
        self.reservation.finals_delivered_at = timezone.now()
        self.reservation.save()
        self.reservation.finals_delivered_at = None
        self.reservation.save()
        self.reservation.refresh_from_db()
        self.assertIsNone(self.reservation.finals_delivered_at)

    def test_unlock_proofing_after_delivery_does_not_raise(self):
        self.reservation.finalize_proofing()
        self.reservation.finals_delivered_at = timezone.now()
        self.reservation.save()
        self.reservation.unlock_proofing()
        self.reservation.refresh_from_db()
        self.assertFalse(self.reservation.is_proofing_finalized)
        self.assertIsNotNone(self.reservation.finals_delivered_at)

    def test_status_change_after_delivery_does_not_raise(self):
        self.reservation.finalize_proofing()
        self.reservation.finals_delivered_at = timezone.now()
        self.reservation.save()
        self.reservation.change_status(Reservation.STATUS_NOSHOW, user=self.user)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, Reservation.STATUS_NOSHOW)
        self.assertIsNotNone(self.reservation.finals_delivered_at)

    def test_new_reservation_delivered_but_not_finalized_is_rejected(self):
        reservation = Reservation(
            user=self.user, service=self.service, specialist=self.specialist,
            date=self.future_monday, time=time_cls(11, 0), finals_delivered_at=timezone.now(),
        )
        with self.assertRaises(ValidationError):
            reservation.full_clean()


class ImageValidationTest(FinalsStateBase):
    def test_every_gallery_enforces_minimum_dimension(self):
        from io import BytesIO
        from PIL import Image as PILImage
        from django.core.files.uploadedfile import SimpleUploadedFile

        buffer = BytesIO()
        PILImage.new('RGB', (300, 300), color='red').save(buffer, format='JPEG')
        upload = SimpleUploadedFile('tiny.jpg', buffer.getvalue(), content_type='image/jpeg')
        image = Image(gallery=self.proofing_gallery, order=0, image=upload)
        with self.assertRaises(ValidationError):
            image.full_clean()


class ReservationPhaseTest(FinalsStateBase):
    def test_phase_is_delivered_when_delivered_at_set(self):
        self.reservation.finalize_proofing()
        self.reservation.finals_delivered_at = timezone.now()
        self.reservation.save()
        self.assertEqual(self.reservation.phase, Reservation.PHASE_FINALS_DELIVERED)
        self.assertTrue(
            Reservation.objects.filter(
                Reservation.phase_query(Reservation.PHASE_FINALS_DELIVERED), pk=self.reservation.pk,
            ).exists()
        )

    def test_phase_is_editing_when_finalized_and_not_delivered(self):
        self.reservation.finalize_proofing()
        self.assertEqual(self.reservation.phase, Reservation.PHASE_EDITING)
        self.assertTrue(
            Reservation.objects.filter(
                Reservation.phase_query(Reservation.PHASE_EDITING), pk=self.reservation.pk,
            ).exists()
        )

    def test_delivered_reservation_matches_only_the_delivered_query(self):
        self.reservation.finalize_proofing()
        self.reservation.finals_delivered_at = timezone.now()
        self.reservation.save()
        for phase in (Reservation.PHASE_EDITING, Reservation.PHASE_AWAITING_REVIEW,
                      Reservation.PHASE_GALLERY_UPLOADED, Reservation.STATUS_ACTIVE):
            self.assertFalse(
                Reservation.objects.filter(Reservation.phase_query(phase), pk=self.reservation.pk).exists(),
                phase,
            )

    def test_phase_is_awaiting_review_when_gallery_set_and_review_flag_on(self):
        self.reservation.need_client_review = True
        self.reservation.save()
        self.assertEqual(self.reservation.phase, Reservation.PHASE_AWAITING_REVIEW)

    def test_phase_is_gallery_uploaded_when_review_flag_off(self):
        self.assertEqual(self.reservation.phase, Reservation.PHASE_GALLERY_UPLOADED)

    def test_phase_falls_back_to_status_when_no_gallery(self):
        reservation = Reservation.objects.create(
            user=self.user, service=self.service, specialist=self.specialist,
            date=self.future_monday, time=time_cls(12, 0),
        )
        self.assertEqual(reservation.phase, Reservation.STATUS_ACTIVE)


class ReservationAdminFinalsTest(FinalsStateBase):
    def setUp(self):
        super().setUp()
        self.superuser = CustomUser.objects.create_superuser(
            phone_number='0877777771', email='admin-f@example.com', password='password123',
        )
        self.client.force_login(self.superuser)
        self.url = reverse('admin:main_app_reservation_change', args=[self.reservation.pk])

    def _post(self, **extra):
        data = {
            'date': self.reservation.date.isoformat(),
            'time': '10:00',
            'user': self.user.pk,
            'status': Reservation.STATUS_ACTIVE,
            'service': self.service.pk,
            'specialist': self.specialist.pk,
            'additional_text': '',
            'gallery': self.proofing_gallery.pk,
            '_save': '1',
        }
        data.update(extra)
        return self.client.post(self.url, data)

    def test_finals_delivered_at_is_editable(self):
        admin_instance = ReservationAdmin(Reservation, django_admin.site)
        self.assertNotIn('finals_delivered_at', admin_instance.readonly_fields)
        self.assertNotIn('final_gallery', str(admin_instance.fieldsets))

    def test_setting_delivered_without_finalized_proofing_is_a_validation_error(self):
        response = self._post(finals_delivered_at_0='2026-01-01', finals_delivered_at_1='10:00:00')
        self.assertEqual(response.status_code, 200)
        self.assertIn('finals_delivered_at', response.context['adminform'].form.errors)
        self.reservation.refresh_from_db()
        self.assertIsNone(self.reservation.finals_delivered_at)

    def test_setting_delivered_after_finalized_proofing_works(self):
        self.reservation.finalize_proofing()
        response = self._post(finals_delivered_at_0='2026-01-01', finals_delivered_at_1='10:00:00')
        self.assertEqual(response.status_code, 302)
        self.reservation.refresh_from_db()
        self.assertIsNotNone(self.reservation.finals_delivered_at)

    def test_clearing_delivered_in_the_admin_works(self):
        self.reservation.finalize_proofing()
        self.reservation.finals_delivered_at = timezone.now()
        self.reservation.save()
        response = self._post(finals_delivered_at_0='', finals_delivered_at_1='')
        self.assertEqual(response.status_code, 302)
        self.reservation.refresh_from_db()
        self.assertIsNone(self.reservation.finals_delivered_at)

    def test_unlock_action_skips_delivered_reservations(self):
        self.reservation.finalize_proofing()
        self.reservation.finals_delivered_at = timezone.now()
        self.reservation.save()
        request = RequestFactory().post('/admin/main_app/reservation/')
        unlock_photo_proofing(
            ReservationAdmin(Reservation, django_admin.site), request,
            Reservation.objects.filter(pk=self.reservation.pk),
        )
        self.reservation.refresh_from_db()
        self.assertTrue(self.reservation.is_proofing_finalized)

    def test_unlock_action_still_unlocks_undelivered_reservations(self):
        self.reservation.finalize_proofing()
        request = RequestFactory().post('/admin/main_app/reservation/')
        unlock_photo_proofing(
            ReservationAdmin(Reservation, django_admin.site), request,
            Reservation.objects.filter(pk=self.reservation.pk),
        )
        self.reservation.refresh_from_db()
        self.assertFalse(self.reservation.is_proofing_finalized)


@override_settings(IS_PHOTOGRAPHER_WEBSITE=True)
class ClientProfileDeliveredLineTest(FinalsStateBase):
    def setUp(self):
        super().setUp()
        Reservation.all_objects.filter(pk=self.reservation.pk).update(
            date=timezone.localdate() - timedelta(days=3), status=Reservation.STATUS_COMPLETED,
            proofing_finalized_at=timezone.now(),
        )
        self.client.force_login(self.user)

    def _mark_delivered(self):
        Reservation.all_objects.filter(pk=self.reservation.pk).update(
            finals_delivered_at=timezone.now().replace(year=2026, month=3, day=14),
        )

    def test_delivered_line_is_shown_with_the_date(self):
        self._mark_delivered()
        response = self.client.get(reverse('profile_page'))
        self.assertContains(response, 'Финалните снимки са предадени на')
        self.assertContains(response, '14.03.2026')

    def test_no_line_when_not_delivered(self):
        response = self.client.get(reverse('profile_page'))
        self.assertNotContains(response, 'Финалните снимки са предадени')

    def test_line_hidden_when_photographer_mode_is_off(self):
        self._mark_delivered()
        with override_settings(IS_PHOTOGRAPHER_WEBSITE=False):
            response = self.client.get(reverse('profile_page'))
        self.assertNotContains(response, 'Финалните снимки са предадени')

    def test_profile_has_no_download_button(self):
        self._mark_delivered()
        response = self.client.get(reverse('profile_page'))
        self.assertNotContains(response, 'final-gallery')
        self.assertNotContains(response, 'Финални снимки</')


@override_settings(IS_PHOTOGRAPHER_WEBSITE=True)
class OldFinalUrlsAreGoneTest(FinalsStateBase):
    def test_old_download_urls_return_404(self):
        self.client.force_login(self.user)
        for path in (
            f'/profile/reservations/{self.reservation.pk}/final-gallery/',
            f'/profile/reservations/{self.reservation.pk}/final-gallery/1/',
        ):
            self.assertEqual(self.client.get(path).status_code, 404, path)

    def test_url_names_are_removed(self):
        for name, args in (
            ('final_gallery_download', [1]), ('final_gallery_image', [1, 1]),
        ):
            with self.assertRaises(NoReverseMatch):
                reverse(name, args=args)

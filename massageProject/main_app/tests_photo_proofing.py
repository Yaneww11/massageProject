from datetime import time as time_cls, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from massageProject.accounts.models import CustomUser
from massageProject.main_app.models import (
    Gallery, Image, ImageProof, PhotoLabel, Reservation, Service, Specialist, WorkingHours,
)


class ProofingModelsBase(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            phone_number='0888111111', email='client@example.com', password='pass12345',
        )
        self.service = Service.objects.create(
            name='Massage', description='d', price=50, duration_in_minutes=60, short_description='s',
        )
        self.specialist = Specialist.objects.create(
            name='Maria', description='d', phone_number='0888111112', email='maria@example.com',
        )
        candidate = timezone.localdate() + timedelta(days=7)
        while candidate.weekday() != 0:
            candidate += timedelta(days=1)
        self.future_monday = candidate
        WorkingHours.objects.create(
            specialist=self.specialist, day_of_week=0, start_time=time_cls(9, 0), end_time=time_cls(17, 0),
        )
        self.gallery = Gallery.objects.create(gallery_type=Gallery.TYPE_RESERVATION)
        self.image = Image.objects.create(gallery=self.gallery, order=0, alt_text='Photo 1', image='gallery/test.jpg')
        self.reservation = Reservation.objects.create(
            user=self.user, service=self.service, specialist=self.specialist,
            date=self.future_monday, time=time_cls(10, 0), gallery=self.gallery,
        )


class ReservationProofingFieldsTest(ProofingModelsBase):
    def test_new_reservation_is_not_finalized(self):
        self.assertFalse(self.reservation.is_proofing_finalized)
        self.assertIsNone(self.reservation.proofing_finalized_at)
        self.assertIsNone(self.reservation.proofing_finalized_by)

    def test_finalize_proofing_stamps_audit_fields(self):
        self.reservation.finalize_proofing(self.user)
        self.reservation.refresh_from_db()
        self.assertTrue(self.reservation.is_proofing_finalized)
        self.assertIsNotNone(self.reservation.proofing_finalized_at)
        self.assertEqual(self.reservation.proofing_finalized_by, self.user)

    def test_unlock_proofing_clears_audit_fields_only(self):
        image_proof = ImageProof.objects.create(image=self.image, is_marked=True, comment='keep this')
        self.reservation.finalize_proofing(self.user)
        self.reservation.unlock_proofing()
        self.reservation.refresh_from_db()
        self.assertFalse(self.reservation.is_proofing_finalized)
        self.assertIsNone(self.reservation.proofing_finalized_by)
        image_proof.refresh_from_db()
        self.assertTrue(image_proof.is_marked)
        self.assertEqual(image_proof.comment, 'keep this')


class PhotoLabelModelTest(ProofingModelsBase):
    def test_cap_must_be_at_least_one(self):
        label = PhotoLabel(gallery=self.gallery, name='За печат', cap=0, order=0)
        with self.assertRaises(ValidationError):
            label.full_clean()

    def test_valid_label_saves(self):
        label = PhotoLabel.objects.create(gallery=self.gallery, name='За печат', cap=5, order=0)
        self.assertEqual(str(label), 'За печат')


class ImageProofModelTest(ProofingModelsBase):
    def test_defaults_to_unmarked_no_comment(self):
        proof = ImageProof.objects.create(image=self.image)
        self.assertFalse(proof.is_marked)
        self.assertEqual(proof.comment, '')
        self.assertEqual(list(proof.labels.all()), [])

    def test_can_attach_multiple_labels(self):
        label_a = PhotoLabel.objects.create(gallery=self.gallery, name='За печат', cap=5, order=0)
        label_b = PhotoLabel.objects.create(gallery=self.gallery, name='Албум', cap=10, order=1)
        proof = ImageProof.objects.create(image=self.image, is_marked=True)
        proof.labels.add(label_a, label_b)
        self.assertEqual(set(proof.labels.all()), {label_a, label_b})


from django.contrib import admin as django_admin
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory

from massageProject.main_app.admin import GalleryAdmin, ReservationAdmin, unlock_photo_proofing


class ReservationAdminUnlockActionTest(ProofingModelsBase):
    def setUp(self):
        super().setUp()
        self.admin_instance = ReservationAdmin(Reservation, django_admin.site)
        self.factory = RequestFactory()

    def test_unlock_action_clears_finalized_reservation(self):
        self.reservation.finalize_proofing(self.user)
        request = self.factory.post('/admin/main_app/reservation/')
        unlock_photo_proofing(self.admin_instance, request, Reservation.objects.filter(pk=self.reservation.pk))
        self.reservation.refresh_from_db()
        self.assertFalse(self.reservation.is_proofing_finalized)

    def test_unlock_action_skips_non_finalized_reservation(self):
        request = self.factory.post('/admin/main_app/reservation/')
        unlock_photo_proofing(self.admin_instance, request, Reservation.objects.filter(pk=self.reservation.pk))
        self.reservation.refresh_from_db()
        self.assertFalse(self.reservation.is_proofing_finalized)

    def test_reservation_admin_exposes_proofing_audit_fields(self):
        self.assertIn('proofing_finalized_at', self.admin_instance.readonly_fields)
        self.assertIn('proofing_finalized_by', self.admin_instance.readonly_fields)


class GalleryAdminPhotoLabelInlineTest(ProofingModelsBase):
    def test_gallery_admin_has_photo_label_inline(self):
        admin_instance = GalleryAdmin(Gallery, django_admin.site)
        inline_models = [inline.model for inline in admin_instance.inlines]
        self.assertIn(PhotoLabel, inline_models)


from django.test import Client
from django.urls import reverse


class PhotoProofingGalleryContextTest(ProofingModelsBase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.user)
        self.label = PhotoLabel.objects.create(gallery=self.gallery, name='За печат', cap=5, order=0)

    def test_unfinalized_reservation_context(self):
        response = self.client.get(reverse('photo_proofing'))
        self.assertFalse(response.context['is_finalized'])
        photo = response.context['photos'][0]
        self.assertFalse(photo['is_marked'])
        self.assertEqual(photo['comment'], '')
        self.assertEqual(response.context['labels_config'][0]['key'], self.label.pk)

    def test_finalized_reservation_context_reflects_marks_and_labels(self):
        proof = ImageProof.objects.create(image=self.image, is_marked=True, comment='crop tighter')
        proof.labels.add(self.label)
        self.reservation.finalize_proofing(self.user)
        response = self.client.get(reverse('photo_proofing'))
        self.assertTrue(response.context['is_finalized'])
        photo = response.context['photos'][0]
        self.assertTrue(photo['is_marked'])
        self.assertEqual(photo['comment'], 'crop tighter')
        self.assertEqual(photo['label_keys'], [self.label.pk])


class ProofingEndpointsTest(ProofingModelsBase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.user)
        self.label = PhotoLabel.objects.create(gallery=self.gallery, name='За печат', cap=1, order=0)
        self.other_user = CustomUser.objects.create_user(
            phone_number='0888111113', email='other@example.com', password='pass12345',
        )

    def test_mark_toggles_on_then_off(self):
        url = reverse('photo_proofing_mark', args=[self.image.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(ImageProof.objects.get(image=self.image).is_marked)
        response = self.client.post(url)
        self.assertFalse(ImageProof.objects.get(image=self.image).is_marked)

    def test_mark_rejects_non_owner(self):
        self.client.force_login(self.other_user)
        response = self.client.post(reverse('photo_proofing_mark', args=[self.image.pk]))
        self.assertEqual(response.status_code, 404)

    def test_mark_rejects_when_finalized(self):
        self.reservation.finalize_proofing(self.user)
        response = self.client.post(reverse('photo_proofing_mark', args=[self.image.pk]))
        self.assertEqual(response.status_code, 403)

    def test_label_toggle_respects_cap(self):
        second_image = Image.objects.create(gallery=self.gallery, order=1, alt_text='Photo 2', image='gallery/test2.jpg')
        url_1 = reverse('photo_proofing_label', args=[self.image.pk, self.label.pk])
        url_2 = reverse('photo_proofing_label', args=[second_image.pk, self.label.pk])
        self.client.post(reverse('photo_proofing_mark', args=[self.image.pk]))
        self.client.post(reverse('photo_proofing_mark', args=[second_image.pk]))
        self.assertEqual(self.client.post(url_1).status_code, 200)
        response = self.client.post(url_2)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.label in ImageProof.objects.get(image=second_image).labels.all())

    def test_comment_save_overwrites(self):
        url = reverse('photo_proofing_comment', args=[self.image.pk])
        self.client.post(url, {'content': 'first note'})
        self.client.post(url, {'content': 'second note'})
        self.assertEqual(ImageProof.objects.get(image=self.image).comment, 'second note')

    def test_finalize_requires_at_least_one_mark(self):
        response = self.client.post(reverse('photo_proofing_finalize'))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Reservation.objects.get(pk=self.reservation.pk).is_proofing_finalized)

    def test_finalize_succeeds_with_a_mark(self):
        self.client.post(reverse('photo_proofing_mark', args=[self.image.pk]))
        response = self.client.post(reverse('photo_proofing_finalize'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Reservation.objects.get(pk=self.reservation.pk).is_proofing_finalized)

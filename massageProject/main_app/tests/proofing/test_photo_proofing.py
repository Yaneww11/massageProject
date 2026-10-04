from datetime import time as time_cls, timedelta

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
        self.gallery = Gallery.objects.create(gallery_type=Gallery.TYPE_PROOFING)
        self.image = Image.objects.create(gallery=self.gallery, order=0, alt_text='Photo 1', image='gallery/test.jpg')
        self.reservation = Reservation.objects.create(
            user=self.user, service=self.service, specialist=self.specialist,
            date=self.future_monday, time=time_cls(10, 0), gallery=self.gallery,
            need_client_review=True,
        )


class ReservationProofingFieldsTest(ProofingModelsBase):
    def test_new_reservation_is_not_finalized(self):
        self.assertFalse(self.reservation.is_proofing_finalized)
        self.assertIsNone(self.reservation.proofing_finalized_at)

    def test_finalize_proofing_stamps_audit_fields(self):
        self.reservation.finalize_proofing()
        self.reservation.refresh_from_db()
        self.assertTrue(self.reservation.is_proofing_finalized)
        self.assertIsNotNone(self.reservation.proofing_finalized_at)

    def test_unlock_proofing_clears_audit_fields_only(self):
        image_proof = ImageProof.objects.create(image=self.image, is_marked=True, comment='keep this')
        self.reservation.finalize_proofing()
        self.reservation.unlock_proofing()
        self.reservation.refresh_from_db()
        self.assertFalse(self.reservation.is_proofing_finalized)
        image_proof.refresh_from_db()
        self.assertTrue(image_proof.is_marked)
        self.assertEqual(image_proof.comment, 'keep this')


class PhotoLabelModelTest(ProofingModelsBase):
    def test_valid_label_saves(self):
        label = PhotoLabel.objects.create(gallery=self.gallery, name='За печат', order=0)
        self.assertEqual(str(label), 'За печат')


class ImageProofModelTest(ProofingModelsBase):
    def test_defaults_to_unmarked_no_comment(self):
        proof = ImageProof.objects.create(image=self.image)
        self.assertFalse(proof.is_marked)
        self.assertEqual(proof.comment, '')
        self.assertEqual(list(proof.labels.all()), [])

    def test_can_attach_multiple_labels(self):
        label_a = PhotoLabel.objects.create(gallery=self.gallery, name='За печат', order=0)
        label_b = PhotoLabel.objects.create(gallery=self.gallery, name='Албум', order=1)
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
        self.reservation.finalize_proofing()
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
        self.label = PhotoLabel.objects.create(gallery=self.gallery, name='За печат', order=0)

    def test_unfinalized_reservation_context(self):
        response = self.client.get(reverse('photo_proofing'))
        self.assertFalse(response.context['is_finalized'])
        photo = response.context['photos'][0]
        self.assertFalse(photo['is_marked'])
        self.assertEqual(photo['comment'], '')
        self.assertEqual(response.context['labels_config'][0]['key'], self.label.pk)

    def test_reservation_not_flagged_for_review_redirects_to_profile(self):
        self.reservation.need_client_review = False
        self.reservation.save(update_fields=['need_client_review'])
        response = self.client.get(reverse('photo_proofing'))
        self.assertRedirects(response, reverse('profile_page'))

    def test_gallery_without_images_redirects_to_profile(self):
        self.image.delete()
        response = self.client.get(reverse('photo_proofing'))
        self.assertRedirects(response, reverse('profile_page'))

    def test_finalizing_hides_reservation_from_next_visit(self):
        self.client.post(reverse('photo_proofing_mark', args=[self.image.pk]))
        self.client.post(reverse('photo_proofing_finalize'))
        response = self.client.get(reverse('photo_proofing'))
        self.assertRedirects(response, reverse('profile_page'))

    def test_finalized_reservation_context_reflects_marks_and_labels(self):
        proof = ImageProof.objects.create(image=self.image, is_marked=True, comment='crop tighter')
        proof.labels.add(self.label)
        self.reservation.finalize_proofing()
        # finalize_proofing() clears need_client_review, which would otherwise
        # hide this reservation from the client entirely; re-open it here to
        # check the context data itself still reflects the finalized state.
        self.reservation.need_client_review = True
        self.reservation.save(update_fields=['need_client_review'])
        response = self.client.get(reverse('photo_proofing'))
        self.assertTrue(response.context['is_finalized'])
        photo = response.context['photos'][0]
        self.assertTrue(photo['is_marked'])
        self.assertEqual(photo['comment'], 'crop tighter')
        self.assertEqual(photo['label_keys'], [self.label.pk])


class ProfileProofTeaserTest(ProofingModelsBase):
    """The profile page only advertises photo proofing when there is
    something to review."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.user)

    def test_teaser_shown_when_photos_await_review(self):
        response = self.client.get(reverse('profile_page'))
        self.assertContains(response, 'proof-teaser-card')

    def test_teaser_hidden_when_review_is_not_requested(self):
        self.reservation.need_client_review = False
        self.reservation.save(update_fields=['need_client_review'])
        response = self.client.get(reverse('profile_page'))
        self.assertNotContains(response, 'proof-teaser-card')

    def test_teaser_hidden_when_gallery_has_no_images(self):
        self.image.delete()
        response = self.client.get(reverse('profile_page'))
        self.assertNotContains(response, 'proof-teaser-card')

    def test_newer_empty_gallery_does_not_hide_an_older_reviewable_one(self):
        empty_gallery = Gallery.objects.create(gallery_type=Gallery.TYPE_PROOFING)
        Reservation.objects.create(
            user=self.user, service=self.service, specialist=self.specialist,
            date=self.future_monday + timedelta(days=7), time=time_cls(11, 0),
            gallery=empty_gallery, need_client_review=True,
        )
        response = self.client.get(reverse('profile_page'))
        self.assertContains(response, 'proof-teaser-card')
        response = self.client.get(reverse('photo_proofing'))
        self.assertEqual(response.context['reservation'], self.reservation)

    def test_teaser_hidden_after_finalizing(self):
        self.client.post(reverse('photo_proofing_mark', args=[self.image.pk]))
        self.client.post(reverse('photo_proofing_finalize'))
        response = self.client.get(reverse('profile_page'))
        self.assertNotContains(response, 'proof-teaser-card')

    def test_finalizing_leaves_a_success_message_for_the_profile_page(self):
        self.client.post(reverse('photo_proofing_mark', args=[self.image.pk]))
        self.client.post(reverse('photo_proofing_finalize'))
        response = self.client.get(reverse('profile_page'))
        self.assertContains(response, 'Изборът ви е финализиран')


class ProofingEndpointsTest(ProofingModelsBase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.user)
        self.label = PhotoLabel.objects.create(gallery=self.gallery, name='За печат', order=0)
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
        self.reservation.finalize_proofing()
        response = self.client.post(reverse('photo_proofing_mark', args=[self.image.pk]))
        self.assertEqual(response.status_code, 403)

    def test_label_can_be_attached_to_every_photo(self):
        second_image = Image.objects.create(gallery=self.gallery, order=1, alt_text='Photo 2', image='gallery/test2.jpg')
        url_1 = reverse('photo_proofing_label', args=[self.image.pk, self.label.pk])
        url_2 = reverse('photo_proofing_label', args=[second_image.pk, self.label.pk])
        self.client.post(reverse('photo_proofing_mark', args=[self.image.pk]))
        self.client.post(reverse('photo_proofing_mark', args=[second_image.pk]))
        self.assertEqual(self.client.post(url_1).status_code, 200)
        self.assertEqual(self.client.post(url_2).status_code, 200)
        self.assertIn(self.label, ImageProof.objects.get(image=self.image).labels.all())
        self.assertIn(self.label, ImageProof.objects.get(image=second_image).labels.all())

    def test_comment_save_overwrites(self):
        url = reverse('photo_proofing_comment', args=[self.image.pk])
        self.client.post(url, {'content': 'first note'})
        self.client.post(url, {'content': 'second note'})
        self.assertEqual(ImageProof.objects.get(image=self.image).comment, 'second note')

    def test_comment_over_2000_chars_is_rejected(self):
        url = reverse('photo_proofing_comment', args=[self.image.pk])
        response = self.client.post(url, {'content': 'x' * 2001})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])

    def test_finalize_requires_at_least_one_mark(self):
        response = self.client.post(reverse('photo_proofing_finalize'))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Reservation.objects.get(pk=self.reservation.pk).is_proofing_finalized)

    def test_finalize_succeeds_with_a_mark(self):
        self.client.post(reverse('photo_proofing_mark', args=[self.image.pk]))
        response = self.client.post(reverse('photo_proofing_finalize'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Reservation.objects.get(pk=self.reservation.pk).is_proofing_finalized)


import shutil
import tempfile
import time
from io import BytesIO
from unittest import mock

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image as PILImage


def _make_test_jpeg_bytes():
    buffer = BytesIO()
    PILImage.new('RGB', (400, 300), color=(120, 160, 200)).save(buffer, format='JPEG')
    buffer.seek(0)
    return buffer.read()


class ProofImageServingViewTest(ProofingModelsBase):
    def setUp(self):
        super().setUp()
        self.tmp_media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_media, ignore_errors=True)
        self.storage_override = override_settings(STORAGES={
            'default': {
                'BACKEND': 'django.core.files.storage.FileSystemStorage',
                'OPTIONS': {'location': self.tmp_media, 'base_url': '/media/'},
            },
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
        })
        self.storage_override.enable()
        self.addCleanup(self.storage_override.disable)
        self.image.image.save('real.jpg', SimpleUploadedFile('real.jpg', _make_test_jpeg_bytes()), save=True)
        self.client = Client()
        self.client.force_login(self.user)

    def _token(self, image_id=None, user_id=None):
        from massageProject.main_app.views import _proof_image_token
        return _proof_image_token(image_id or self.image.pk, user_id or self.user.pk)

    def test_valid_token_redirects_to_derivative(self):
        from massageProject.main_app.views import _proof_derivative_path
        response = self.client.get(reverse('photo_proofing_image', args=[self._token()]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(default_storage.exists(_proof_derivative_path(self.image.pk, self.user.pk)))

    def test_derivative_is_only_generated_once(self):
        from massageProject.main_app.views import _proof_derivative_path
        url = reverse('photo_proofing_image', args=[self._token()])
        self.client.get(url)
        path = _proof_derivative_path(self.image.pk, self.user.pk)
        first_mtime = default_storage.get_modified_time(path)
        self.client.get(url)
        second_mtime = default_storage.get_modified_time(path)
        self.assertEqual(first_mtime, second_mtime)

    def test_expired_token_is_rejected(self):
        from massageProject.main_app.views import PROOF_IMAGE_MAX_AGE
        token = self._token()
        future = time.time() + PROOF_IMAGE_MAX_AGE + 1
        with mock.patch('time.time', return_value=future):
            response = self.client.get(reverse('photo_proofing_image', args=[token]))
        self.assertEqual(response.status_code, 403)

    def test_tampered_token_is_rejected(self):
        response = self.client.get(reverse('photo_proofing_image', args=[self._token() + 'x']))
        self.assertEqual(response.status_code, 403)

    def test_token_for_a_different_user_is_rejected(self):
        token = self._token(user_id=self._make_other_user().pk)
        response = self.client.get(reverse('photo_proofing_image', args=[token]))
        self.assertEqual(response.status_code, 403)

    def test_token_for_image_owned_by_another_user_is_rejected(self):
        other_user = self._make_other_user()
        other_gallery = Gallery.objects.create(gallery_type=Gallery.TYPE_PROOFING)
        other_image = Image.objects.create(
            gallery=other_gallery, order=0, alt_text='Other photo', image='gallery/other.jpg',
        )
        Reservation.objects.create(
            user=other_user, service=self.service, specialist=self.specialist,
            date=self.future_monday, time=time_cls(11, 0), gallery=other_gallery,
        )
        # Token is validly signed for self.user (the logged-in requester), but points at an
        # image that belongs to a different user's reservation.
        token = self._token(image_id=other_image.pk, user_id=self.user.pk)
        response = self.client.get(reverse('photo_proofing_image', args=[token]))
        self.assertEqual(response.status_code, 404)

    def _make_other_user(self):
        return CustomUser.objects.create_user(
            phone_number='0888111114', email='third@example.com', password='pass12345',
        )

    def test_cross_origin_referer_is_rejected(self):
        response = self.client.get(
            reverse('photo_proofing_image', args=[self._token()]),
            HTTP_REFERER='https://evil-example.com/steal',
        )
        self.assertEqual(response.status_code, 403)

    def test_missing_referer_is_allowed(self):
        response = self.client.get(reverse('photo_proofing_image', args=[self._token()]))
        self.assertEqual(response.status_code, 302)

    def test_matching_referer_is_allowed(self):
        response = self.client.get(
            reverse('photo_proofing_image', args=[self._token()]),
            HTTP_REFERER='http://testserver/profile/photos/',
        )
        self.assertEqual(response.status_code, 302)


class DerivativeCacheInvalidationTest(ProofingModelsBase):
    def setUp(self):
        super().setUp()
        self.tmp_media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_media, ignore_errors=True)
        self.storage_override = override_settings(STORAGES={
            'default': {
                'BACKEND': 'django.core.files.storage.FileSystemStorage',
                'OPTIONS': {'location': self.tmp_media, 'base_url': '/media/'},
            },
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
        })
        self.storage_override.enable()
        self.addCleanup(self.storage_override.disable)

    def test_replacing_image_file_clears_its_cached_derivatives(self):
        stale_path = f'proof_derivatives/{self.image.pk}/{self.user.pk}.jpg'
        default_storage.save(stale_path, ContentFile(b'stale-bytes'))
        self.image.image.save('new.jpg', SimpleUploadedFile('new.jpg', _make_test_jpeg_bytes()), save=True)
        self.assertFalse(default_storage.exists(stale_path))


class ProofSignedUrlTest(TestCase):
    """The GCS backend's signature is url(name, parameters=None) and forwards
    `parameters` to blob.generate_signed_url(), so an expiring URL is requested
    with parameters={'expiration': ...} — not the expire= kwarg that used to be
    passed here, which raised TypeError on every single request."""

    def test_signed_url_requests_a_fifteen_minute_expiration(self):
        from massageProject.main_app.views import PROOF_URL_TTL, _signed_proof_url

        backend = mock.Mock()
        backend.url.return_value = 'https://signed.example/x.jpg'
        with mock.patch('massageProject.main_app.views.default_storage', backend):
            url = _signed_proof_url('proof_derivatives/1/abc.jpg')

        self.assertEqual(url, 'https://signed.example/x.jpg')
        backend.url.assert_called_once_with(
            'proof_derivatives/1/abc.jpg', parameters={'expiration': PROOF_URL_TTL},
        )
        self.assertEqual(PROOF_URL_TTL, timedelta(minutes=15))

    def test_no_warning_logged_when_backend_supports_expiring_urls(self):
        backend = mock.Mock()
        backend.url.return_value = 'https://signed.example/x.jpg'
        from massageProject.main_app.views import _signed_proof_url

        with mock.patch('massageProject.main_app.views.default_storage', backend):
            with self.assertNoLogs('massageProject.main_app.views', level='WARNING'):
                _signed_proof_url('proof_derivatives/1/abc.jpg')

    def test_falls_back_to_plain_url_for_backends_without_parameters(self):
        """Local dev runs FileSystemStorage, whose url() takes no parameters."""
        from massageProject.main_app.views import _signed_proof_url

        class PlainStorage:
            def url(self, name):
                return '/media/' + name

        with mock.patch('massageProject.main_app.views.default_storage', PlainStorage()):
            with self.assertLogs('massageProject.main_app.views', level='WARNING'):
                url = _signed_proof_url('proof_derivatives/1/abc.jpg')
        self.assertEqual(url, '/media/proof_derivatives/1/abc.jpg')


class ProofingPaginationTest(ProofingModelsBase):
    """A 400-photo gallery used to emit 400 <img> tags with no lazy-loading and
    no pagination, firing 400 concurrent requests at two workers."""

    PAGE_SIZE = 60

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.user)
        # self.image (order 0) already exists on the gallery; add 79 more.
        self.images = [self.image] + [
            Image.objects.create(gallery=self.gallery, order=i, image=f'gallery/photos/p{i}.webp')
            for i in range(1, 80)
        ]
        self.total = len(self.images)

    def _mark(self, image):
        ImageProof.objects.create(image=image, is_marked=True)

    def test_first_page_holds_only_one_page_of_photos(self):
        response = self.client.get(reverse('photo_proofing'))
        self.assertEqual(len(response.context['photos']), self.PAGE_SIZE)
        self.assertTrue(response.context['page_obj'].has_next())

    def test_second_page_holds_the_remainder(self):
        response = self.client.get(reverse('photo_proofing'), {'page': 2})
        self.assertEqual(len(response.context['photos']), self.total - self.PAGE_SIZE)
        self.assertFalse(response.context['page_obj'].has_next())

    def test_photos_lazy_load(self):
        response = self.client.get(reverse('photo_proofing'))
        self.assertContains(response, 'loading="lazy"')

    def test_totals_are_gallery_wide_not_page_scoped(self):
        for image in self.images[:70]:
            self._mark(image)
        response = self.client.get(reverse('photo_proofing'))
        self.assertEqual(response.context['total_photos'], self.total)
        # 70 marked, but only 60 photos are on this page — the count must not
        # collapse to what the page happens to contain.
        self.assertEqual(response.context['marked_total'], 70)

    def test_frame_numbering_continues_across_pages(self):
        response = self.client.get(reverse('photo_proofing'), {'page': 2})
        self.assertEqual(response.context['page_obj'].start_index(), self.PAGE_SIZE + 1)
        self.assertContains(response, 'Кадър %d' % (self.PAGE_SIZE + 1))

    def test_marked_filter_spans_the_whole_gallery_not_just_page_one(self):
        """A photo marked at position 75 must show up on page 1 of the marked
        filter — the bug that page-scoped client-side filtering would cause."""
        late_image = self.images[75]
        self._mark(late_image)
        response = self.client.get(reverse('photo_proofing'), {'filter': 'marked'})
        ids = [p['id'] for p in response.context['photos']]
        self.assertEqual(ids, [late_image.pk])

    def test_finalized_filter_is_empty_while_proofing_is_open(self):
        self._mark(self.images[0])
        response = self.client.get(reverse('photo_proofing'), {'filter': 'finalized'})
        self.assertEqual(response.context['photos'], [])

    def test_marked_filter_is_empty_once_finalized(self):
        self._mark(self.images[0])
        self.reservation.finalize_proofing()
        self.reservation.need_client_review = True
        self.reservation.save(update_fields=['need_client_review'])
        response = self.client.get(reverse('photo_proofing'), {'filter': 'marked'})
        self.assertEqual(response.context['photos'], [])
        response = self.client.get(reverse('photo_proofing'), {'filter': 'finalized'})
        self.assertEqual(len(response.context['photos']), 1)

    def test_marking_a_photo_on_a_later_page_still_works(self):
        late_image = self.images[75]
        response = self.client.post(reverse('photo_proofing_mark', args=[late_image.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['is_marked'])

    def test_out_of_range_page_falls_back_to_the_last_page(self):
        response = self.client.get(reverse('photo_proofing'), {'page': 99})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['page_obj'].number, 2)


class ProofFrameNumberingTest(ProofingModelsBase):
    """Finding 7: frame numbers were derived from the position on the filtered
    page, so the same photo was "Кадър 1" on the marked tab and "Кадър 8" on
    the all tab. A client's comment naming a frame has to mean one photo."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.user)
        self.images = [self.image] + [
            Image.objects.create(gallery=self.gallery, order=i, image=f'gallery/photos/p{i}.webp')
            for i in range(1, 10)
        ]

    def _numbers(self, **params):
        response = self.client.get(reverse('photo_proofing'), params)
        return {p['id']: p['number'] for p in response.context['photos']}

    def test_number_is_the_position_in_the_whole_gallery(self):
        numbers = self._numbers()
        self.assertEqual([numbers[img.pk] for img in self.images], list(range(1, 11)))

    def test_number_is_unchanged_by_the_marked_filter(self):
        late = self.images[7]
        ImageProof.objects.create(image=late, is_marked=True)
        self.assertEqual(self._numbers(filter='marked')[late.pk], 8)

    def test_number_is_unchanged_by_pagination(self):
        all_numbers = self._numbers()
        self.assertEqual(self._numbers(page=1)[self.images[9].pk], all_numbers[self.images[9].pk])

    def test_numbering_ignores_gaps_in_the_order_column(self):
        """Admin-curated galleries have non-contiguous `order` values, so the
        number is a position, not the raw order field."""
        Image.objects.filter(pk=self.images[1].pk).update(order=99)
        numbers = self._numbers()
        self.assertEqual(sorted(numbers.values()), list(range(1, 11)))

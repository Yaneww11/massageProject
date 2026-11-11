from django.core.files.storage import default_storage
from django.test import override_settings
from django.urls import reverse

from massageProject.main_app.models import Gallery, Image, ImageProof, Reservation
from massageProject.main_app.tests.helpers import make_uploaded_jpeg
from massageProject.main_app.tests.proofing.test_marked_photos import MarkedPhotosTestBase
from massageProject.main_app.views import _proof_derivative_path


class ClientPreviewTestBase(MarkedPhotosTestBase):
    def setUp(self):
        super().setUp()
        # Awaiting client review: the client is being asked to pick photos.
        Reservation.all_objects.filter(pk=self.reservation.pk).update(need_client_review=True)
        self.reservation.refresh_from_db()
        self.preview_url = reverse('client_preview', args=[self.reservation.pk])


class ClientPreviewAccessTest(ClientPreviewTestBase):
    def test_specialist_sees_clients_page_read_only(self):
        self.client.force_login(self.specialist_user)
        response = self.client.get(self.preview_url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_preview'])
        self.assertEqual(response.context['reservation'], self.reservation)
        self.assertContains(response, 'Преглед като клиент')
        self.assertContains(response, 'const readOnly = true;')
        # Visible like the client's, but switched off.
        self.assertContains(response, '<button type="button" id="proof-finalize-open" class="btn btn-primary" disabled>')
        self.assertContains(response, '<button type="button" id="proof-drawer-save" class="btn btn-primary" disabled>')
        self.assertContains(response, 'crop tighter')
        self.assertContains(response, 'За печат')
        photos = {p['id']: p for p in response.context['photos']}
        self.assertTrue(photos[self.marked_image.pk]['is_marked'])
        self.assertEqual(photos[self.marked_image.pk]['label_keys'], [self.label.pk])
        self.assertEqual(
            photos[self.marked_image.pk]['url'],
            reverse('client_preview_image', args=[self.reservation.pk, self.marked_image.pk]),
        )

    def test_watermark_carries_the_clients_identity(self):
        self.client.force_login(self.specialist_user)
        response = self.client.get(self.preview_url)
        self.assertEqual(
            response.context['watermark_identifier'], f'Maria Petrova · #{self.reservation.pk}',
        )

    def test_staff_can_preview_any_specialists_reservation(self):
        self.client.force_login(self.staff_user)
        self.assertEqual(self.client.get(self.preview_url).status_code, 200)

    def test_other_specialist_is_forbidden(self):
        self.client.force_login(self.other_specialist_user)
        self.assertEqual(self.client.get(self.preview_url).status_code, 403)

    def test_client_without_workflow_permission_is_forbidden(self):
        self.client.force_login(self.client_user)
        self.assertEqual(self.client.get(self.preview_url).status_code, 403)

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(self.preview_url)
        self.assertEqual(response.status_code, 302)

    def test_not_awaiting_review_is_404(self):
        Reservation.all_objects.filter(pk=self.reservation.pk).update(need_client_review=False)
        self.client.force_login(self.specialist_user)
        self.assertEqual(self.client.get(self.preview_url).status_code, 404)

    def test_empty_gallery_still_opens(self):
        Image.objects.filter(gallery=self.gallery).delete()
        self.client.force_login(self.specialist_user)
        response = self.client.get(self.preview_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_photos'], 0)

    def test_not_photographer_website_is_404(self):
        with override_settings(IS_PHOTOGRAPHER_WEBSITE=False):
            self.client.force_login(self.specialist_user)
            self.assertEqual(self.client.get(self.preview_url).status_code, 404)


class ClientPreviewImageTest(ClientPreviewTestBase):
    def test_serves_the_clients_own_proof_derivative(self):
        self.client.force_login(self.specialist_user)
        response = self.client.get(
            reverse('client_preview_image', args=[self.reservation.pk, self.unmarked_image.pk]),
        )
        self.assertEqual(response.status_code, 302)
        client_path = _proof_derivative_path(self.unmarked_image.pk, self.client_user.pk)
        self.assertTrue(default_storage.exists(client_path))
        specialist_path = _proof_derivative_path(self.unmarked_image.pk, self.specialist_user.pk)
        self.assertFalse(default_storage.exists(specialist_path))

    def test_image_from_another_gallery_is_404(self):
        other_gallery = Gallery.objects.create(gallery_type=Gallery.TYPE_PROOFING)
        stray = Image.objects.create(gallery=other_gallery, order=0, image=make_uploaded_jpeg('stray.jpg'))
        self.client.force_login(self.specialist_user)
        response = self.client.get(reverse('client_preview_image', args=[self.reservation.pk, stray.pk]))
        self.assertEqual(response.status_code, 404)

    def test_other_specialist_is_forbidden(self):
        self.client.force_login(self.other_specialist_user)
        response = self.client.get(
            reverse('client_preview_image', args=[self.reservation.pk, self.marked_image.pk]),
        )
        self.assertEqual(response.status_code, 403)


class ClientPreviewCannotChangeProofsTest(ClientPreviewTestBase):
    def test_specialist_cannot_mark_clients_photo(self):
        self.client.force_login(self.specialist_user)
        response = self.client.post(reverse('photo_proofing_mark', args=[self.unmarked_image.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertFalse(ImageProof.objects.filter(image=self.unmarked_image, is_marked=True).exists())

    def test_specialist_cannot_finalize_for_client(self):
        self.client.force_login(self.specialist_user)
        response = self.client.post(reverse('photo_proofing_finalize'))
        self.assertEqual(response.status_code, 404)
        self.reservation.refresh_from_db()
        self.assertIsNone(self.reservation.proofing_finalized_at)


class ClientPreviewTableButtonTest(ClientPreviewTestBase):
    def test_button_shown_for_reservation_awaiting_review(self):
        self.client.force_login(self.specialist_user)
        response = self.client.get(reverse('profile_page'))
        self.assertContains(response, self.preview_url)

    def test_button_hidden_once_review_is_no_longer_requested(self):
        Reservation.all_objects.filter(pk=self.reservation.pk).update(need_client_review=False)
        self.client.force_login(self.specialist_user)
        response = self.client.get(reverse('profile_page'))
        self.assertNotContains(response, self.preview_url)

import io
import zipfile
from datetime import time as time_cls, timedelta
from unittest import mock

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from massageProject.accounts.models import CustomUser
from massageProject.main_app.models import Gallery, HomePage, Image, Reservation, Service, Specialist, WorkingHours


def make_zip(names=('a.jpg', 'b.png'), extra=None):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        for name in names:
            archive.writestr(name, b'data-' + name.encode())
        for name, content in (extra or {}).items():
            archive.writestr(name, content)
    return buffer.getvalue()


class FinalZipBase(TestCase):
    def setUp(self):
        ct = ContentType.objects.get_for_model(Reservation)
        view_all = Permission.objects.get(content_type=ct, codename='view_all_reservations')
        view_specialist = Permission.objects.get(content_type=ct, codename='view_specialist_reservations')
        self.service = Service.objects.create(
            name='Photoshoot', description='d', price=100, duration_in_minutes=60, short_description='s',
        )
        self.specialist_user = CustomUser.objects.create_user(
            phone_number='0888400001', email='sp@example.com', password='pass12345',
        )
        self.specialist = Specialist.objects.create(
            name='Ivan', description='d', phone_number='0888400002', email='ivan@example.com',
            user=self.specialist_user,
        )
        self.specialist_user.user_permissions.add(view_specialist)
        self.other_user = CustomUser.objects.create_user(
            phone_number='0888400006', email='other@example.com', password='pass12345',
        )
        self.other_user.user_permissions.add(view_specialist)
        Specialist.objects.create(
            name='Zora', description='d', phone_number='0888400007', email='z@example.com', user=self.other_user,
        )
        self.staff_user = CustomUser.objects.create_user(
            phone_number='0888400004', email='staff@example.com', password='pass12345',
        )
        self.staff_user.user_permissions.add(view_all)
        self.client_user = CustomUser.objects.create_user(
            phone_number='0888400005', email='client@example.com', password='pass12345',
        )
        candidate = timezone.localdate() - timedelta(days=3)
        while candidate.weekday() != 0:
            candidate -= timedelta(days=1)
        self.reservation = Reservation.objects.create(
            user=self.client_user, service=self.service, specialist=self.specialist,
            date=candidate, time=time_cls(10, 0), status=Reservation.STATUS_COMPLETED,
        )
        self.reservation.finalize_proofing()
        self.http = Client()
        self.http.force_login(self.specialist_user)
        self.url = reverse('final_gallery_upload')

    def _post(self, content=None, reservation=None, name='finals.zip', max_mb=None):
        content = make_zip() if content is None else content
        data = {
            'reservation': (reservation or self.reservation).pk,
            'zip_file': SimpleUploadedFile(name, content, content_type='application/zip'),
        }
        if max_mb is not None:
            with override_settings(FINAL_ZIP_MAX_MB=max_mb):
                return self.http.post(self.url, data)
        return self.http.post(self.url, data)


@override_settings(IS_PHOTOGRAPHER_WEBSITE=True)
class FinalZipUploadViewTest(FinalZipBase):
    def _assert_rejected(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['upload_form'].errors)
        self.assertEqual(len(mail.outbox), 0)
        self.reservation.refresh_from_db()
        self.assertIsNone(self.reservation.finals_delivered_at)

    def test_get_preselects_reservation(self):
        response = self.http.get(f'{self.url}?reservation_id={self.reservation.pk}')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'accept=".zip,application/zip"')
        self.assertEqual(str(response.context['upload_form'].initial['reservation']), str(self.reservation.pk))

    def test_happy_path_sends_attachment_and_stamps(self):
        content = make_zip()
        HomePage.get_solo()  # email branding lazily creates the singleton and its gallery
        galleries, images = Gallery.objects.count(), Image.objects.count()
        response = self._post(content)
        self.assertRedirects(response, reverse('profile_page'), fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ['client@example.com'])
        self.assertEqual(len(message.attachments), 1)
        filename, payload, mimetype = message.attachments[0]
        self.assertEqual(filename, f'final-photos-reservation-{self.reservation.pk}.zip')
        self.assertEqual(mimetype, 'application/zip')
        self.assertEqual(payload, content)
        self.reservation.refresh_from_db()
        self.assertIsNotNone(self.reservation.finals_delivered_at)
        self.assertEqual(Gallery.objects.count(), galleries)
        self.assertEqual(Image.objects.count(), images)

    def test_email_no_longer_links_to_a_download(self):
        self._post()
        message = mail.outbox[0]
        self.assertNotIn('final-gallery', message.body)
        self.assertNotIn('final-gallery', message.alternatives[0][0])
        self.assertIn('прикачени', message.body)

    def test_resend_keeps_original_stamp(self):
        stamp = timezone.now() - timedelta(days=1)
        Reservation.objects.filter(pk=self.reservation.pk).update(finals_delivered_at=stamp)
        self._post()
        self.assertEqual(len(mail.outbox), 1)
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.finals_delivered_at, stamp)

    def test_over_size_limit_rejected(self):
        self._assert_rejected(self._post(make_zip(), max_mb=0))

    def test_not_a_zip_rejected(self):
        self._assert_rejected(self._post(b'not a zip at all'))

    def test_corrupt_zip_rejected(self):
        content = bytearray(make_zip(extra={'c.jpg': b'x' * 2000}))
        content[40] ^= 0xFF  # flip a byte inside the first member's data
        self._assert_rejected(self._post(bytes(content)))

    def test_empty_zip_rejected(self):
        self._assert_rejected(self._post(make_zip(names=())))

    def test_zip_with_only_junk_rejected(self):
        self._assert_rejected(self._post(make_zip(names=('__MACOSX/a.jpg', '.DS_Store', 'folder/'))))

    def test_non_image_member_rejected(self):
        self._assert_rejected(self._post(make_zip(names=('a.jpg', 'notes.txt'))))

    def test_junk_entries_are_ignored(self):
        content = make_zip(names=('a.jpg', '__MACOSX/._a.jpg', 'shots/.DS_Store', 'shots/'))
        self._post(content)
        self.assertEqual(len(mail.outbox), 1)

    def test_client_without_email_rejected(self):
        CustomUser.objects.filter(pk=self.client_user.pk).update(email='')
        self._assert_rejected(self._post())

    def test_proofing_not_finalized_rejected(self):
        Reservation.all_objects.filter(pk=self.reservation.pk).update(proofing_finalized_at=None)
        self._assert_rejected(self._post())

    def test_send_failure_shows_error_and_stamps_nothing(self):
        with mock.patch('django.core.mail.backends.locmem.EmailBackend.send_messages', side_effect=RuntimeError):
            response = self._post()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['upload_form'].non_field_errors())
        self.reservation.refresh_from_db()
        self.assertIsNone(self.reservation.finals_delivered_at)

    def test_other_specialist_forbidden(self):
        self.http.force_login(self.other_user)
        self.assertEqual(self._post().status_code, 403)
        self.assertEqual(len(mail.outbox), 0)

    def test_client_forbidden(self):
        self.http.force_login(self.client_user)
        self.assertEqual(self.http.get(self.url).status_code, 403)
        self.assertEqual(self._post().status_code, 403)

    def test_staff_allowed(self):
        self.http.force_login(self.staff_user)
        self._post()
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(IS_PHOTOGRAPHER_WEBSITE=False)
    def test_inert_when_photographer_mode_off(self):
        self.assertEqual(self.http.get(self.url).status_code, 404)
        self.assertEqual(self._post().status_code, 404)
        self.assertEqual(len(mail.outbox), 0)


@override_settings(IS_PHOTOGRAPHER_WEBSITE=True)
class FinalsTableButtonsTest(FinalZipBase):
    def _table(self):
        html = self.http.get(reverse('profile_page'), {'phase': 'all'}).content.decode()
        return html

    def test_undelivered_row_shows_upload_button(self):
        html = self._table()
        self.assertIn('Качи финали', html)
        self.assertNotIn('Изпрати отново</a>', html)

    def test_delivered_row_shows_resend_button(self):
        Reservation.objects.filter(pk=self.reservation.pk).update(finals_delivered_at=timezone.now())
        html = self._table()
        self.assertIn('Изпрати отново</a>', html)
        self.assertNotIn('Качи финали', html)

    def test_no_email_hides_both(self):
        CustomUser.objects.filter(pk=self.client_user.pk).update(email='')
        html = self._table()
        self.assertNotIn('Качи финали', html)
        self.assertNotIn('Изпрати отново</a>', html)

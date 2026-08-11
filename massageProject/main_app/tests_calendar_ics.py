from datetime import time as time_cls, timedelta, datetime
from zoneinfo import ZoneInfo

from django.test import TestCase, RequestFactory
from django.utils import timezone

from massageProject.accounts.models import CustomUser
from massageProject.main_app.ics import build_reservation_ics
from massageProject.main_app.models import BusinessInfo, Reservation, Service, Specialist, WorkingHours


class BuildReservationIcsTest(TestCase):
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
        BusinessInfo.objects.create(
            name='Studio', description='d', address='123 Main St, Sofia',
            email_address='studio@example.com', main_image='business/test.jpg',
        )
        self.reservation = Reservation.objects.create(
            user=self.user, service=self.service, specialist=self.specialist,
            date=self.future_monday, time=time_cls(10, 0),
        )
        # Django's test runner auto-adds 'testserver' (only) to ALLOWED_HOSTS
        # for the duration of the test run, so that's the only host name
        # request.get_host() will accept here without raising DisallowedHost.
        self.request = RequestFactory().get('/')
        self.request.META['HTTP_HOST'] = 'testserver'

    def _expected_utc(self, local_time):
        local_dt = datetime.combine(self.future_monday, local_time, tzinfo=ZoneInfo('Europe/Sofia'))
        return local_dt.astimezone(ZoneInfo('UTC')).strftime('%Y%m%dT%H%M%SZ')

    def test_dtstart_and_dtend_are_utc_converted(self):
        content = build_reservation_ics(self.request, self.reservation)
        self.assertIn(f'DTSTART:{self._expected_utc(time_cls(10, 0))}', content)
        self.assertIn(f'DTEND:{self._expected_utc(self.reservation.end_time)}', content)

    def test_contains_one_hour_reminder(self):
        content = build_reservation_ics(self.request, self.reservation)
        self.assertIn('BEGIN:VALARM', content)
        self.assertIn('TRIGGER:-PT1H', content)

    def test_summary_contains_service_name(self):
        content = build_reservation_ics(self.request, self.reservation)
        self.assertIn('SUMMARY:Massage', content)

    def test_location_contains_escaped_business_address(self):
        content = build_reservation_ics(self.request, self.reservation)
        self.assertIn('LOCATION:123 Main St\\, Sofia', content)

    def test_location_empty_when_no_business_info(self):
        from django.core.cache import cache
        BusinessInfo.objects.all().delete()
        # get_cached_business_info() only invalidates its cache entry on
        # post_save, not on delete — clear it explicitly so this test doesn't
        # depend on incidental signal timing from setUp()'s create() call.
        cache.delete('business_info_singleton')
        content = build_reservation_ics(self.request, self.reservation)
        lines = content.split('\r\n')
        location_line = next(line for line in lines if line.startswith('LOCATION:'))
        self.assertEqual(location_line, 'LOCATION:')

    def test_uid_contains_reservation_pk_and_host(self):
        content = build_reservation_ics(self.request, self.reservation)
        self.assertIn(f'UID:reservation-{self.reservation.pk}@testserver', content)

    def test_additional_text_comma_and_newline_are_escaped(self):
        self.reservation.additional_text = 'Bring towel, please.\nAnd water.'
        self.reservation.save()
        content = build_reservation_ics(self.request, self.reservation)
        description_line = next(
            line for line in content.split('\r\n') if line.startswith('DESCRIPTION:')
        )
        self.assertIn('Bring towel\\, please.\\nAnd water.', description_line)

    def test_uses_crlf_line_endings(self):
        content = build_reservation_ics(self.request, self.reservation)
        self.assertNotIn('\r\n\n', content)
        self.assertTrue(content.endswith('\r\n'))
        self.assertIn('BEGIN:VCALENDAR\r\n', content)

    def test_additional_text_with_crlf_is_escaped(self):
        # Browsers normalize textarea submissions to CRLF, not bare LF.
        # This test verifies that CRLF in additional_text is correctly escaped.
        self.reservation.additional_text = 'Bring towel, please.\r\nAnd water.'
        self.reservation.save()
        content = build_reservation_ics(self.request, self.reservation)
        description_line = next(
            line for line in content.split('\r\n') if line.startswith('DESCRIPTION:')
        )
        # Both CRLF and bare LF should result in escaped \n in output
        self.assertIn('Bring towel\\, please.\\nAnd water.', description_line)

    def test_additional_text_with_bare_cr_is_escaped(self):
        # Verify that even a bare carriage return (not part of CRLF) is normalized and escaped.
        self.reservation.additional_text = 'Bring towel, please.\rAnd water.'
        self.reservation.save()
        content = build_reservation_ics(self.request, self.reservation)
        description_line = next(
            line for line in content.split('\r\n') if line.startswith('DESCRIPTION:')
        )
        # Bare \r should also be escaped as \n
        self.assertIn('Bring towel\\, please.\\nAnd water.', description_line)

# Add to Calendar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire up the already-stubbed "Добави в календар" button on the client profile page's next-booking card so it downloads a universal `.ics` file the client can open in Google Calendar, Apple Calendar, Outlook, or their phone's default calendar app.

**Architecture:** A pure-function ICS builder (`massageProject/main_app/ics.py`) converts a `Reservation` into RFC 5545 text, using Python's stdlib `zoneinfo` to convert Europe/Sofia-local reservation times to UTC. A thin, ownership-checked Django view serves that text as a `text/calendar` download. The existing disabled button in `templates/pages/my_profile.html` becomes a plain link to that view — no JavaScript involved.

**Tech Stack:** Django views/urls (existing patterns), Python stdlib `zoneinfo` (no new dependency), Django `TestCase`/`Client` for tests.

## Global Constraints

- Event times are Europe/Sofia local, converted to UTC in the `.ics` output (`DTSTART`/`DTEND` end in `Z`) — spec: "Design > ICS generation".
- No new third-party dependency — spec: "Non-goals".
- Only the existing next-booking hero card gets the button wired up; no per-row button on the upcoming-reservations table — spec: "Non-goals".
- `.ics` fields (`SUMMARY`, `LOCATION`, `DESCRIPTION`) must escape `\`, `,`, `;`, and embedded newlines per RFC 5545, and the file must use `\r\n` line endings — spec: "Design > ICS generation".
- One `VALARM` block with `TRIGGER:-PT1H` (1-hour-before reminder) — spec: "Design > ICS generation".
- `UID` is `reservation-{pk}@{host}`, stable per reservation — spec: "Design > ICS generation".
- Ownership check mirrors the existing `if reservation.user != request.user: raise PermissionDenied` pattern (see `_blocked_by_edit_window` in `massageProject/main_app/views.py`) — spec: "Design > Endpoint".

---

### Task 1: ICS builder module

**Files:**
- Create: `massageProject/main_app/ics.py`
- Test: `massageProject/main_app/tests_calendar_ics.py`

**Interfaces:**
- Consumes: `massageProject.main_app.context_processors.get_cached_homepage()` (returns a `HomePage` instance, never `None` — it auto-creates via `get_or_create`), `massageProject.main_app.context_processors.get_cached_business_info()` (returns a `BusinessInfo` instance or `None` if none exists), `Reservation` fields `date`, `time`, `end_time` (property), `service.name`, `specialist.name`, `additional_text`, `pk`.
- Produces: `build_reservation_ics(request, reservation) -> str` — later tasks (Task 2) call this and wrap the return value in an `HttpResponse`.

This task builds and directly tests the text-generation logic, with no HTTP/view layer involved yet.

- [ ] **Step 1: Write the failing tests**

Create `massageProject/main_app/tests_calendar_ics.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source venv/bin/activate && python manage.py test massageProject.main_app.tests_calendar_ics -v 2`
Expected: `ModuleNotFoundError: No module named 'massageProject.main_app.ics'` (or import error) for every test.

- [ ] **Step 3: Write the implementation**

Create `massageProject/main_app/ics.py`:

```python
from datetime import datetime
from zoneinfo import ZoneInfo

from massageProject.main_app.context_processors import get_cached_business_info, get_cached_homepage

RESERVATION_TIMEZONE = ZoneInfo('Europe/Sofia')
UTC = ZoneInfo('UTC')


def _escape_ics_text(value):
    return (
        value.replace('\\', '\\\\')
        .replace(',', '\\,')
        .replace(';', '\\;')
        .replace('\n', '\\n')
    )


def _format_ics_datetime(local_date, local_time):
    local_dt = datetime.combine(local_date, local_time, tzinfo=RESERVATION_TIMEZONE)
    return local_dt.astimezone(UTC).strftime('%Y%m%dT%H%M%SZ')


def build_reservation_ics(request, reservation):
    homepage = get_cached_homepage()
    business_info = get_cached_business_info()

    dtstart = _format_ics_datetime(reservation.date, reservation.time)
    dtend = _format_ics_datetime(reservation.date, reservation.end_time)
    dtstamp = datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')

    summary = _escape_ics_text(f'{reservation.service.name} — {homepage.brand_name}')
    location = _escape_ics_text(business_info.address) if business_info else ''

    description_parts = [reservation.specialist.name]
    if reservation.additional_text:
        description_parts.append(reservation.additional_text)
    description = _escape_ics_text('\n'.join(description_parts))

    uid = f'reservation-{reservation.pk}@{request.get_host()}'

    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        f'PRODID:-//{_escape_ics_text(homepage.brand_name)}//Reservation Calendar//BG',
        'BEGIN:VEVENT',
        f'UID:{uid}',
        f'DTSTAMP:{dtstamp}',
        f'DTSTART:{dtstart}',
        f'DTEND:{dtend}',
        f'SUMMARY:{summary}',
        f'LOCATION:{location}',
        f'DESCRIPTION:{description}',
        'BEGIN:VALARM',
        'ACTION:DISPLAY',
        'DESCRIPTION:Reminder',
        'TRIGGER:-PT1H',
        'END:VALARM',
        'END:VEVENT',
        'END:VCALENDAR',
    ]
    return '\r\n'.join(lines) + '\r\n'
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `source venv/bin/activate && python manage.py test massageProject.main_app.tests_calendar_ics -v 2`
Expected: all 8 tests in `BuildReservationIcsTest` PASS.

- [ ] **Step 5: Commit**

```bash
git add massageProject/main_app/ics.py massageProject/main_app/tests_calendar_ics.py
git commit -m "feat: add ICS builder for reservation calendar export"
```

---

### Task 2: View + URL

**Files:**
- Modify: `massageProject/main_app/views.py` (insert new view after the `ProfilePage` class, i.e. after line 499's `context['next_client_reservation'] = today_and_future.order_by('date', 'time').first()`, before `def _get_current_proofing_reservation(user):` at line 502)
- Modify: `massageProject/main_app/urls.py`
- Test: `massageProject/main_app/tests_calendar_ics.py` (append a new test class)

**Interfaces:**
- Consumes: `build_reservation_ics(request, reservation) -> str` from Task 1.
- Produces: URL name `reservation_calendar_ics`, taking one arg `reservation_id` — Task 3's template link depends on this exact name.

- [ ] **Step 1: Write the failing tests**

Append to `massageProject/main_app/tests_calendar_ics.py` (same file, new class — needs `Client`/`reverse`):

```python
from django.test import Client
from django.urls import reverse


class ReservationCalendarViewTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            phone_number='0888111111', email='client@example.com', password='pass12345',
        )
        self.other_user = CustomUser.objects.create_user(
            phone_number='0888111113', email='other@example.com', password='pass12345',
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
        WorkingHours.objects.create(
            specialist=self.specialist, day_of_week=0, start_time=time_cls(9, 0), end_time=time_cls(17, 0),
        )
        self.reservation = Reservation.objects.create(
            user=self.user, service=self.service, specialist=self.specialist,
            date=candidate, time=time_cls(10, 0),
        )
        self.client = Client()

    def test_owner_downloads_ics(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('reservation_calendar_ics', args=[self.reservation.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/calendar; charset=utf-8')
        self.assertIn(f'reservation-{self.reservation.pk}.ics', response['Content-Disposition'])
        self.assertIn('attachment', response['Content-Disposition'])

    def test_non_owner_forbidden(self):
        self.client.force_login(self.other_user)
        response = self.client.get(reverse('reservation_calendar_ics', args=[self.reservation.pk]))
        self.assertEqual(response.status_code, 403)

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse('reservation_calendar_ics', args=[self.reservation.pk]))
        self.assertEqual(response.status_code, 302)

    def test_missing_reservation_404s(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('reservation_calendar_ics', args=[999999]))
        self.assertEqual(response.status_code, 404)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source venv/bin/activate && python manage.py test massageProject.main_app.tests_calendar_ics.ReservationCalendarViewTest -v 2`
Expected: FAIL — `NoReverseMatch: Reverse for 'reservation_calendar_ics' not found`.

- [ ] **Step 3: Add the view**

In `massageProject/main_app/views.py`, `HttpResponse` isn't imported yet (only `JsonResponse, Http404` from `django.http` on line 22) — add it:

```python
from django.http import JsonResponse, Http404
```
becomes:
```python
from django.http import HttpResponse, JsonResponse, Http404
```

And add the ICS builder import (extend the existing `context_processors` import on line 25):

```python
from massageProject.main_app.context_processors import get_cached_homepage
```
becomes:
```python
from massageProject.main_app.context_processors import get_cached_homepage
from massageProject.main_app.ics import build_reservation_ics
```

Then insert this view after line 499 (end of `ProfilePage._add_calendar_context`), before `def _get_current_proofing_reservation(user):`:

```python
@login_required
def download_reservation_ics(request, reservation_id):
    reservation = get_object_or_404(Reservation, pk=reservation_id)
    if reservation.user != request.user:
        raise PermissionDenied
    ics_content = build_reservation_ics(request, reservation)
    response = HttpResponse(ics_content, content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="reservation-{reservation.pk}.ics"'
    return response
```

- [ ] **Step 4: Add the URL**

In `massageProject/main_app/urls.py`, add `download_reservation_ics` to the view import on line 3-6:

```python
from massageProject.main_app.views import Index, ServicesDashboard, ReservationPage, AboutPage, ProfilePage, \
    edit_reservation, delete_reservation, PrivacyPolicyView, check_availability, AllCommentsView, \
    submit_comment, GalleryView, GalleryAlbumView, PhotoProofingGallery, mark_photo, toggle_photo_label, \
    save_photo_comment, finalize_photo_proofing, serve_proof_image, download_reservation_ics
```

Add the path after line 17's `path('profile/', ProfilePage.as_view(), name='profile_page'),`:

```python
    path('profile/reservations/<int:reservation_id>/calendar/', download_reservation_ics, name='reservation_calendar_ics'),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `source venv/bin/activate && python manage.py test massageProject.main_app.tests_calendar_ics -v 2`
Expected: all tests in both `BuildReservationIcsTest` and `ReservationCalendarViewTest` PASS (12 total).

- [ ] **Step 6: Commit**

```bash
git add massageProject/main_app/views.py massageProject/main_app/urls.py massageProject/main_app/tests_calendar_ics.py
git commit -m "feat: add reservation calendar .ics download endpoint"
```

---

### Task 3: Template wiring

**Files:**
- Modify: `templates/pages/my_profile.html:92-95`

**Interfaces:**
- Consumes: URL name `reservation_calendar_ics` from Task 2, template context var `next_reservation` (already provided by `ProfilePage.get_context_data`, unchanged by this plan).
- Produces: nothing consumed by later tasks — this is the last task.

- [ ] **Step 1: Replace the disabled button with a working link**

In `templates/pages/my_profile.html`, replace:

```html
          <button class="btn-calendar" disabled>
            <i class="fas fa-calendar-plus"></i> {% trans "Добави в календар" %}
          </button>
```

with:

```html
          <a href="{% url 'reservation_calendar_ics' next_reservation.id %}" class="btn-calendar">
            <i class="fas fa-calendar-plus"></i> {% trans "Добави в календар" %}
          </a>
```

- [ ] **Step 2: Verify the full suite still passes**

Run: `source venv/bin/activate && python manage.py test`
Expected: same pass/fail counts as the pre-existing baseline (no new failures introduced — the profile page's own tests, if any, should still pass; this is a template-only change with no new Python logic to unit-test).

- [ ] **Step 3: Manual check**

Run: `source venv/bin/activate && python manage.py runserver`, log in as a client with an active reservation, open `/profile/`, and click "Добави в календар". Confirm a `reservation-<id>.ics` file downloads, and opening it (e.g. double-click, or `cat` it) shows a valid `VEVENT` with the correct date/time, service name, business address, and a 1-hour reminder.

- [ ] **Step 4: Commit**

```bash
git add templates/pages/my_profile.html
git commit -m "feat: wire up add-to-calendar button on profile page"
```

---

## Self-Review Notes

- **Spec coverage:** endpoint + ownership check (Task 2), ICS generation with UTC conversion/escaping/VALARM/UID (Task 1), template wiring (Task 3), known-limitation (documented in spec, no code needed), non-goals respected (no per-row buttons, no new dependency, no Google-specific link).
- **Type consistency:** `build_reservation_ics(request, reservation) -> str` signature is identical across Task 1's definition, Task 1's tests, and Task 2's view usage. URL name `reservation_calendar_ics` matches across Task 2's `path()` and Task 3's `{% url %}` tag.
- **No placeholders:** every step has real, runnable code.

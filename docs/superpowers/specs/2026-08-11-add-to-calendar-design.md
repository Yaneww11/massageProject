# Add to Calendar — Design

Date: 2026-08-11

## Context

`templates/pages/my_profile.html`'s "next booking" hero card already has a
stubbed, disabled button:

```html
<button class="btn-calendar" disabled>
  <i class="fas fa-calendar-plus"></i> {% trans "Добави в календар" %}
</button>
```

sitting next to a working "Directions" link (a Google Maps search URL built
from `business_info.address`) and an "Промени" (edit) link. This spec wires
that button up so a client can add their upcoming reservation to whatever
calendar app they actually use — Google Calendar, Apple Calendar, Outlook, or
their phone's default calendar — without needing a separate button per
platform.

## Non-goals

- Per-row calendar buttons on the "upcoming reservations" table below the
  hero card — only the existing next-booking card gets wired up.
- Keeping a downloaded/imported event in sync if the client later reschedules
  via `edit_reservation`. This is a one-time snapshot; re-adding after a
  reschedule requires the client to download again. A live-updating event
  would need a CalDAV subscription feed, far out of scope for this feature.
- A Google-Calendar-specific quick-add link. A single universal `.ics`
  download covers Google Calendar (which can import `.ics`) and every other
  calendar app through one code path, avoiding a second mechanism for
  marginal one-tap convenience.
- Any new third-party dependency. Python's stdlib `zoneinfo` is sufficient
  for generating one non-recurring `VEVENT`.

## Design

### Endpoint

New view in `massageProject/main_app/views.py`:

```python
@login_required
def download_reservation_ics(request, reservation_id):
    reservation = get_object_or_404(Reservation, pk=reservation_id)
    if reservation.user != request.user:
        raise PermissionDenied
    ...
    return HttpResponse(ics_content, content_type='text/calendar; charset=utf-8', headers={
        'Content-Disposition': f'attachment; filename="reservation-{reservation.pk}.ics"',
    })
```

The ownership check mirrors the existing pattern in `_blocked_by_edit_window`
(`if reservation.user != request.user: raise PermissionDenied`) — no new
authorization concept introduced.

URL, in `massageProject/main_app/urls.py`, alongside the other
`profile/...` routes:

```python
path('profile/reservations/<int:reservation_id>/calendar/', download_reservation_ics, name='reservation_calendar_ics'),
```

### ICS generation

A single non-recurring `VEVENT`, hand-built as text (no `icalendar` package
needed for one event). Key points:

- **Times**: combine `reservation.date` + `reservation.time` (start) and
  `reservation.date` + `reservation.end_time` (end, already a `Reservation`
  property) as `Europe/Sofia`-local via `zoneinfo.ZoneInfo('Europe/Sofia')`,
  then convert to UTC and emit as `DTSTART:YYYYMMDDTHHMMSSZ` /
  `DTEND:...Z`. Emitting UTC avoids needing to embed a `VTIMEZONE` block and
  is parsed correctly, DST included, by every mainstream calendar app.
- **`SUMMARY`**: service name + business name (fetched via
  `HomePage.get_solo()`, matching how `accounts/emails.py:send_otp_email`
  already pulls branding for outgoing content).
- **`LOCATION`**: `BusinessInfo.address` (same field the existing
  "Directions" link on this card already uses).
- **`DESCRIPTION`**: specialist name, plus `reservation.additional_text` if
  non-empty (the client's own note from booking).
- **`UID`**: `reservation-{pk}@{request.get_host()}` — stable per
  reservation, so calendar apps that dedupe/update-in-place on a repeat
  import of the same UID behave sensibly rather than creating a duplicate.
- **`VALARM`**: one alarm block, `TRIGGER:-PT1H`, `ACTION:DISPLAY` — a
  1-hour-before reminder baked into the event itself, independent of the
  client's calendar app defaults.
- **Formatting**: `\r\n` line endings (required by RFC 5545, and some
  clients like Outlook are strict about it) and escaping of `,`, `;`, `\`,
  and embedded newlines in free-text fields (`SUMMARY`, `LOCATION`,
  `DESCRIPTION`) — `additional_text` is free-form client input, so this
  matters for correctness, not just theoretical compliance.

### Template wiring

`templates/pages/my_profile.html:92-95` — replace the disabled `<button>`
with an `<a>` styled identically to the adjacent action links:

```html
<a href="{% url 'reservation_calendar_ics' next_reservation.id %}" class="btn-calendar">
  <i class="fas fa-calendar-plus"></i> {% trans "Добави в календар" %}
</a>
```

No JavaScript needed — a plain link whose response carries
`Content-Disposition: attachment` triggers the browser/OS's native
"open with Calendar" flow on both desktop and mobile. `next_reservation` is
only ever `active_reservations[0]` (`views.py:440`), i.e. always the
logged-in user's own upcoming reservation, so no extra template-level guard
is needed beyond the view's own ownership check.

## Testing

New test module `massageProject/main_app/tests_calendar_ics.py`, following
the existing `tests_photo_proofing.py` conventions:

- Owner requesting their own reservation's `.ics` → `200`,
  `Content-Type: text/calendar`, correct filename in `Content-Disposition`.
- A different logged-in user requesting someone else's reservation → `403`.
- Anonymous request → redirected to login.
- Content assertions on a known reservation (pick a summer date to exercise
  DST, since Sofia is UTC+3 under EEST): `DTSTART`/`DTEND` match the
  expected UTC-converted values, a `VALARM`/`TRIGGER:-PT1H` block is
  present, `SUMMARY` contains the service name, `LOCATION` contains the
  business address.
- Escaping: an `additional_text` containing a comma and an embedded newline
  produces a file where that field still parses back as a single logical
  value (i.e. the raw comma/newline don't corrupt the surrounding ICS
  structure).

## Known limitation

Downloaded/imported events are a one-time snapshot — rescheduling a
reservation afterward does not update any calendar entry the client already
added. This is accepted as inherent to the `.ics`-download approach rather
than something this feature attempts to solve.
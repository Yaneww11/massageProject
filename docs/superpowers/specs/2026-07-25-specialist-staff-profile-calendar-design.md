# Specialist & Staff Profile Calendar — Design Spec

Date: 2026-07-25

## Goal

`ProfilePage` (`/profile/`) currently only distinguishes two audiences: a
client sees their own bookings, and anyone passing a `has_perm` check
(`main_app.view_all_reservations`) sees a flat, site-wide list of every
reservation with no indication of whose booking it is. There is no way for
a specialist to log in and see their own schedule, and the "staff" branch
is effectively superuser-only because `view_all_reservations` was never
declared as a real Django permission.

This spec adds a third role — **specialist** — with its own read-only
weekly calendar of their bookings, extends the staff branch to browse any
specialist's calendar the same way, and fixes the permission plumbing so
both capabilities are properly assignable through the Django admin instead
of only working for superusers.

## Current state (verified)

- `ProfilePage` (`massageProject/main_app/views.py:324`) is a plain
  `TemplateView` behind `LoginRequiredMixin`. It branches only on
  `user.has_perm('main_app.view_all_reservations')`.
- `view_all_reservations` is **not declared** in any `Meta.permissions` —
  it doesn't exist as a row in `auth_permission`. `has_perm` only returns
  `True` today via Django's superuser short-circuit, so no regular staff
  account can be granted this today.
- `CustomUser` (`massageProject/accounts/models.py`) has no link to
  `Specialist` and no role/flag beyond `is_staff` (which only means
  "can log into the Django admin" and is unrelated to this feature).
- `Specialist` (`massageProject/main_app/models.py:111`) has no link back
  to `CustomUser`.
- No calendar library is loaded anywhere in the project (`base.html` only
  loads Font Awesome and Turnstile). The only existing calendar-like UI is
  a hand-built month date-picker in `reservation.html` for choosing a
  single booking slot — not a multi-event schedule view.
- `WorkingHours` gives one start/end window per `(specialist, day_of_week)`;
  combined with active `Reservation`s this is sufficient to compute a
  specialist's busy/free blocks per day.

## Role resolution

Three mutually exclusive branches, resolved in `ProfilePage.get_context_data`:

```python
specialist = getattr(user, 'specialist_profile', None)
if user.has_perm('main_app.view_all_reservations'):
    role = 'staff'
elif specialist and user.has_perm('main_app.view_specialist_reservations'):
    role = 'specialist'
else:
    role = 'client'
```

- A user needs **both** the `Specialist.user` link **and** the
  `view_specialist_reservations` permission to get the specialist branch —
  either alone falls back to the plain client view.
- If a user somehow qualifies for both `staff` and `specialist` (linked as
  a specialist *and* holds `view_all_reservations`), `staff` wins — it's
  the superset view (browsing any specialist including themselves).
- `client` remains the existing default behavior, completely unchanged.

## Data model changes

**`Specialist.user`** — new field:
```python
user = models.OneToOneField(
    'accounts.CustomUser', null=True, blank=True,
    on_delete=models.SET_NULL, related_name='specialist_profile',
)
```
Structural/access-control field, not rendered as a value on the frontend —
no `help_text` needed per the existing convention for structural FKs.

**`Reservation.Meta.permissions`** — new entry (currently has no
`permissions` at all):
```python
permissions = [
    ('view_all_reservations', 'Can view all reservations across all specialists'),
    ('view_specialist_reservations', 'Can view own specialist reservations'),
]
```
Both become real, admin-assignable permissions. This fixes
`view_all_reservations` so a non-superuser staff account can be granted it
through the standard user/group permission widgets — no other behavior of
the existing (currently superuser-only) staff branch changes other than
now being reachable by non-superusers and gaining the calendar (see below).

One migration adds the field and the permissions.

## Specialist branch (own schedule)

Replaces all client-only sections (photo-proofing teaser, personal stat
cards, next-booking highlight, visit history/reviews) with:

- **Week calendar**: Monday–Sunday columns, hourly gridlines bounded by
  that specialist's `WorkingHours` for each day (a day with no
  `WorkingHours` row renders as "Почивен ден", matching existing wording).
  Reservations render as positioned blocks within the grid.
- **Stat cards**: bookings today, bookings this week, next client
  name/time — same visual pattern as today's client stat cards, different
  data.
- **Booking details on click**: clicking a block opens a small modal
  (reusing the existing vanilla-JS review-modal pattern already in
  `my_profile.html`) showing client name, phone, the service, the client's
  booking note (`additional_text`), and how many past visits that client
  has had with this specialist. Purely a read-only detail view — no new
  write endpoints.
- **Week navigation**: `?week=YYYY-MM-DD` GET param (the Monday of the
  target week); Prev/Next links do a normal full-page reload. Defaults to
  the current week when absent.

## Staff branch (any specialist)

- A `<select>` dropdown of all specialists (GET param `specialist_id`,
  defaulting to the first specialist by name) reloads the page on change.
- Renders the **same week-calendar partial** as the specialist branch,
  parameterized by the selected specialist instead of `request.user`'s own
  link.
- Same stat cards and same click-for-details modal, scoped to whichever
  specialist is selected.
- This entirely replaces the old flat, all-reservations table (which never
  even showed which client a row belonged to).

## Calendar implementation

- New view-level helper (e.g. `_build_week_calendar(specialist, week_start)`
  in `views.py`) that, given a specialist and the Monday of a week, returns
  per-day: date, weekday label, working-hours window (or `None`), and each
  active reservation with a top-offset/height percentage pre-computed for
  CSS positioning (server-side math, no client-side date/time logic).
- New shared template partial, e.g.
  `templates/partials/specialist_calendar.html`, used by both the
  specialist and staff branches.
- New CSS for the grid and booking blocks (added to `my_profile.css`).
- No new JSON endpoint and no calendar library — full-page reloads for
  week/specialist navigation, consistent with this codebase's existing
  server-rendered pattern (e.g. the month picker in `reservation.html`
  hits `/check-availability/` only for slot data, not for its own
  rendering).

## Admin changes

- `SpecialistAdmin` gets the new `user` field (autocomplete or raw-id
  field) so the site owner can link a `Specialist` record to an existing
  `CustomUser` account.
- Permission assignment (`view_all_reservations`,
  `view_specialist_reservations`) uses Django's existing per-user/per-group
  permission widgets already present on `CustomUser`'s admin — no new
  admin UI required for that part.

## Testing plan

- Migration test: new field + both permissions exist and are assignable.
- View tests for `ProfilePage` covering all three branches, including the
  two fallback cases (specialist link without the permission → client;
  permission without a specialist link → client) and the staff-wins
  precedence when both apply.
- Unit tests for the week-calendar helper: Monday-aligned week boundaries,
  day-off handling (no `WorkingHours` row), and the offset/height
  positioning math for reservations within a working-hours window.
- Translation pass (`makemessages -l bg -l en`, fill in new msgids,
  `compilemessages`) for all new UI strings, per `CLAUDE.md`.
- Manual dev-server walkthrough of all three roles (client, specialist,
  staff with the specialist dropdown) before calling the feature done.

## Out of scope

- Any write actions from the calendar itself (status changes, editing) —
  clicking a booking only shows details; existing edit/delete/status flows
  are unchanged and untouched by this feature.
- A combined "all specialists at once" calendar view for staff — staff
  browse one specialist at a time via the dropdown, reusing the specialist
  view.
- Any change to the existing client-facing profile experience — the
  `client` branch's templates, queries, and behavior are unchanged.

# Spec: Time Off — Specialists block hours or days inside their WorkingHours

Status: ready for implementation

## Problem

A Specialist's availability is defined only by recurring `WorkingHours`
(one row per weekday). There is no way to say "Maria is at the doctor Tuesday
14:00–16:00" or "Ivan is away Mon–Fri next week". Clients can therefore book
slots the Specialist won't actually be there for.

## Glossary

**Time Off** (see `CONTEXT.md`): a one-off period — start and end moment,
spanning hours or whole days — during which a Specialist is unavailable even
though it falls inside their WorkingHours. Recurring unavailability is a
WorkingHours change, not Time Off. UI label: **"Отсъствие" / "Отсъствия"**.

## Current state (what the investigation established)

- Availability is computed in **two places that must agree**:
  - `check_availability` (`main_app/views.py:48`) — builds the 30-min slot list
    for the booking page from WorkingHours, 2h lead time, overlap with active
    Reservations.
  - `Reservation.clean()` (`main_app/models.py`) — runs on *every* save
    (`full_clean()` in `save()`), enforcing the same three rules.
- `/profile/` (`ProfilePage`, `views.py:933`) has two non-client roles:
  - **staff** — `main_app.view_all_reservations`; sees all Specialists.
  - **specialist** — user linked via `Specialist.user` (OneToOne,
    `related_name='specialist_profile'`) with
    `main_app.view_specialist_reservations`; sees only their own schedule.
  - Both currently render the header + `partials/specialist_reservations_table.html`.

## Decisions

| # | Decision |
|---|----------|
| 1 | Concept is **Time Off**; UI label "Отсъствие". |
| 2 | **Both** roles manage Time Off on `/profile/`: specialist → only their own; staff → any Specialist (dropdown). |
| 3 | Shape: **one `start` / `end` date-time range**. Covers both "hours" and "days". No recurrence. |
| 4 | Creating Time Off that clashes with an existing **active** Reservation is **refused**; the error lists the clashing reservations. No auto-cancel. |
| 5 | Enforced in `Reservation.clean()` → blocks **everyone** (clients, staff, admin) from booking/rescheduling into it. |
| 6 | In the booking slot picker, Time Off slots look exactly like "taken" (reason not exposed). A day fully covered yields no available slots. |
| 7 | Management is **create + delete** only (no edit). Profile lists **upcoming** entries (incl. currently ongoing). Registered in Django admin too. |
| 8 | Optional private **note** (never shown to clients) + `created_by` / `created_at` audit. |
| 9 | UI: collapsible **"Отсъствия" section above the reservations table**; "Add" opens a modal; compact list with delete buttons. Staff variant shows Specialist name in list + Specialist dropdown in form. |
| 10 | Times in **30-minute steps**. |
| 11 | `end > start`; `start` may be in the past but **`end` must be in the future** ("sick today" case). Overlapping Time Off entries **allowed**. |
| 12 | **No new permission** — reuse `view_all_reservations` / `view_specialist_reservations` + specialist link. |
| 13 | **No notifications**; section **not** gated by `site_config.booking_enabled`. |
| 14 | "All day" checkbox = full calendar days: 00:00 on start date → end of end date (00:00 the following day). |

## Behaviour

### Model `TimeOff` (main_app)

- `specialist` FK → `Specialist` (CASCADE, `related_name='time_off'`)
- `start`, `end` — date-times on 30-min boundaries
- `note` — optional, private
- `created_by` FK → user (SET_NULL), `created_at` auto
- `clean()`:
  - `end > start`
  - both on :00 / :30 (seconds = 0)
  - `end` in the future (only on create — there is no edit)
  - no overlap with an **active** Reservation of the same Specialist
    (`res_start < end and res_end > start`); message lists each clash
    (date, time, service)
- Ordering: `start`.
- Help texts on user-facing fields per CLAUDE.md conventions.

### `Reservation.clean()`

New check (after working hours, alongside overlap) for active, new-or-rescheduled
reservations: if `[start_dt, end_dt)` overlaps any TimeOff of the Specialist →
`ValidationError` (Bulgarian message, e.g. "%(name)s отсъства в избрания час.").

### `check_availability`

Fetch the Specialist's TimeOff entries overlapping the requested date; a slot
overlapping any of them → `available: False, reason: 'taken'`.

### `/profile/` — "Отсъствия" section (staff + specialist roles only)

- Collapsible section above the reservations table.
- List: upcoming/ongoing entries (`end > now`), ordered by `start`; each row
  shows period (formatted as day range or date + time range), note, (staff:
  Specialist name), and a delete button (POST, with confirm).
- "Add" button → modal form:
  - Specialist dropdown (staff only; specialist role is fixed to self)
  - start date, end date
  - "all day" checkbox; when unchecked, start time / end time selects in 30-min steps
  - note (optional)
- Form errors (incl. clash list) re-render in the modal.
- Endpoints: create + delete views, POST-only, `LoginRequiredMixin`,
  permission/ownership check:
  - staff (`view_all_reservations`) → any Specialist
  - specialist → only `user.specialist_profile`
  - anyone else → 403/404
- Design/implementation of the UI done with the `frontend-design` skill, using
  `site_config` colors (CSS variables), fonts, and terminology
  (`specialist_singular` etc.), no hardcoded hex.

### Admin

`TimeOffAdmin`: list display specialist / start / end / note / created_by;
filter by specialist; `created_by` auto-stamped, read-only.

## Out of scope

- Recurring Time Off
- Editing an entry (delete + recreate)
- Notifications / emails
- Auto-cancelling clashing reservations
- Showing reasons to clients

## Test plan (test-first)

New folder `main_app/tests/time_off/`:

1. **Model validation** — end ≤ start, non-30-min times, end in past, clash with
   active reservation refused (message lists it), clash with cancelled/deleted
   reservation allowed, overlapping TimeOff allowed, start-in-past-but-end-future allowed.
2. **`Reservation.clean()`** — booking inside / partially overlapping / touching
   edge of Time Off; reschedule into Time Off refused; unrelated-field edit on an
   existing reservation not blocked; other Specialist's Time Off ignored.
3. **`check_availability`** — slots inside Time Off reported unavailable
   (`reason: 'taken'`); all-day Time Off → no available slots.
4. **Profile views/permissions** — specialist sees/creates/deletes only own;
   staff for any Specialist; client and anonymous refused; specialist can't
   delete another's entry; past entries not listed; section absent for clients.

## Done when

- All tests above pass, full suite green.
- `makemessages` / `compilemessages` run, new strings translated (bg + en).
- Migration created.

# Codebase Audit Findings — 2026-07-23

Read-only audit of `massageProject/`. Four parallel agents investigated correctness bugs,
performance, best-practice/convention violations, and dead code. No code was changed.
Findings below are the ones each agent judged important enough to report; several of the
highest-severity items were independently spot-checked against the actual source before
being included here. This file is findings only — fixes are not scoped or ordered yet.

---

## 1. Correctness bugs

### 1.1 HIGH — Double-booking race condition (TOCTOU)
`main_app/models.py:256-271`, exercised via `main_app/views.py` (`ReservationPage` POST)

`Reservation.clean()`'s overlap check is a plain `SELECT` with no `select_for_update()`,
and nothing wraps the check-then-`save()` sequence in `transaction.atomic()`. There's also
no DB-level uniqueness/exclusion constraint on `(specialist, date, time)`. Two concurrent
requests for the same slot can both pass validation before either commits, producing two
overlapping active reservations for the same specialist/time.
*Verified: confirmed no `select_for_update`/`atomic()` present at models.py:256-271.*

### 1.2 HIGH — Soft-deleted reservations can be resurrected via admin bulk actions
`main_app/admin.py:40-48, 123-145`

`ReservationAdmin.get_queryset` uses `Reservation.all_objects` (line 145), and the
`mark_as_completed`/`mark_as_noshow` bulk actions call `change_status()` on whatever rows
are selected with no guard on current status. `Reservation.clean()` only validates
overlap/lead-time/working-hours when the *new* status is `active` (models.py:230-231), so
a staff user can select a `deleted` (cancelled) reservation and bulk-mark it
completed/no-show — it silently reappears in `Reservation.objects` (the default,
non-deleted manager) and in the client's `ProfilePage` history. No state-machine guard
prevents transitions out of `deleted`.
*Verified: `admin.py:145` confirmed using `all_objects`, no status check in the two actions.*

### 1.3 MEDIUM — Midnight-wraparound bug in working-hours/overlap checks
`main_app/models.py:218-222, 244-254`

`end_time` (and the inline duplicate at line 245) computes
`(datetime.combine(date, time) + duration).time()`, which discards the date component. If
computed end time crosses midnight it wraps to an early value smaller than the real end.
Example: working hours `09:00–23:30`, 60-min service booked at `23:00` → real end is
next-day `00:00`; wrapped `end_time` is `00:00`, so `end_time > hours.end_time`
(`00:00 > 23:30`) is **False** and the booking is wrongly accepted 30 minutes past
closing. The same wraparound affects the overlap loop (`res_end`), so overlap against a
day-spilling reservation can be missed too. `check_availability` (views.py:63-92) does its
slot math with full `datetime` objects and is *not* affected — meaning the UI's suggested
slots and the model's actual save-time validation can disagree at day boundaries.
*Verified against models.py:218-222 and 244-254.*

### 1.4 MEDIUM — `full_clean()` on every save blocks legitimate near-term edits
`main_app/models.py:224-236, 280-282`

`save()` unconditionally calls `full_clean()`. The lead-time check only special-cases
`status != active`, not "is this actually a new booking vs. an edit to an existing one."
Any save of an active reservation whose appointment is within 2 hours — e.g. an admin
fixing a typo in `additional_text`, or reassigning specialist/service — raises
`ValidationError` and blocks the save, even though nothing about timing changed.

### 1.5 LOW-MEDIUM — Unhandled `IntegrityError` possible on OTP registration
`accounts/booking_auth_views.py:127-157`, `accounts/forms.py:91-100`

Between `verify_code` (stores verified email in session) and `register_via_modal`
(`form.save()`), there's no re-check that the email is still unique. A concurrent
registration/claim of the same email can raise an uncaught `IntegrityError`, surfacing as
a 500 instead of the JSON error response this endpoint otherwise always returns.

### 1.6 LOW — Similar unguarded race in phone-number claim flow
`accounts/forms.py:38-54, 130-168`

`PhoneClaimFormMixin.clean_phone_number()` checks `has_usable_password()` on a matched
passwordless user and "claims" it, but nothing locks the row between validation and
`save()`. Two near-simultaneous claims of the same passwordless phone number could both
proceed.

### 1.7 Documentation drift (not a code bug)
`CLAUDE.md` describes model names `MessageReservation`, `Massage`, `Masseur`,
`MessageStudio`. The actual models are `Reservation`, `Service`, `Specialist`,
`BusinessInfo` (main_app/models.py). Worth fixing since it could mislead future changes.
*Verified: `grep "^class " main_app/models.py` confirms actual names.*

No SQL injection, XSS via `|safe`/`mark_safe` on user input, missing CSRF protection, or
IDOR were found — ownership checks on edit/delete/comment views are correctly enforced.

---

## 2. Performance / optimization

### 2.1 N+1 on the reservation write path (hot path — every booking)
`main_app/models.py:257-268`

The overlap check builds `existing_reservations` without `select_related('service')`,
then loops accessing `res.service.duration_in_minutes`. Since `save()` always calls
`full_clean()`, every reservation create/status-change costs 1 query + 1 extra query per
existing active same-day reservation for that specialist.

### 2.2 Uncached DB hits in a context processor that runs on every request
`main_app/context_processors.py:5-29` (`admin_branding`, registered globally in
`TEMPLATES`, `settings.py:135`)

Calls `HomePage.get_solo()` and `BusinessInfo.objects.first()` uncached on every page
render, unlike the adjacent `site_configuration` processor (lines 32-39) which explicitly
caches its singleton for 60s.

### 2.3 Same singleton re-fetched multiple times per request
`views.py:103` (`Index.get`), `views.py:351-352` (`ProfilePage`), `views.py:119`
(`PrivacyPolicyView`) all re-fetch `HomePage`/`BusinessInfo` that the context processor
already fetched for the same request.

### 2.4 N+1 in profile page reservation lists
`views.py:328-334`, rendered in `templates/pages/my_profile.html:132-138, 176`

`active_reservations`/`past_reservations` lack `select_related('service', 'specialist')`;
each row's `r.service.*`/`r.specialist.name` triggers a fresh query. For staff viewing all
reservations this can be dozens of extra queries per page load. (`reviewed_map` in the same
view already uses `select_related` correctly — the fix pattern exists nearby, just not
applied here.)

### 2.5 `check_availability` missing `select_related('service')`
`views.py:57-61, 76-78` — same unindexed-FK-access pattern as 2.1, on an endpoint polled
on every date selection during booking.

### 2.6 Admin bulk actions: per-row work where bulk `.update()` would suffice
`main_app/admin.py:24-34` (`export_reservations_csv`, no `select_related`, 3 extra
queries/row) and `admin.py:40-48` (`mark_as_completed`/`mark_as_noshow` — N individual
`.save()`/`full_clean()` calls; since target status isn't `active`, `clean()`
short-circuits, so a single `.update()` would be safe and correct for these two actions
specifically).

### 2.7 Missing indexes on the hottest-filtered columns
`Reservation.status` and `Reservation.date` (models.py:180-196) have no index despite
being the filter columns for `active()`/`past()`, the admin date filter, and the
`specialist+date+status` lookup used identically in both `check_availability` and
`clean()`'s overlap check. A composite index on `(specialist, date, status)` would serve
both hot paths. `Comment.is_reviewed` also lacks an index despite being filtered +
ordered on in three views.

---

## 3. Best practices / convention violations

`settings.py` was checked and is clean: `SECRET_KEY`/`DEBUG`/`ALLOWED_HOSTS`/
`CSRF_TRUSTED_ORIGINS` come from env vars, secure-cookie/HSTS settings are correctly
gated on `not DEBUG`, no hardcoded secrets found repo-wide.

### 3.2 `list_display` N+1 in accounts admin
`accounts/admin.py:10, 49-54` — `AppUserAdmin.reservations_count` calls
`obj.reservations.count()` per row with no `annotate()`.

### 3.3 Duplicated 24-hour-rule + ownership check
`main_app/views.py:371-413` — `edit_reservation` (374-381) and `delete_reservation`
(405-412) contain byte-for-byte duplicated logic; a future rule change risks being
applied to only one call site.

### 3.4 Status-stamping logic duplicated between model and admin
`main_app/admin.py:147-151` reimplements `Reservation.change_status()`'s stamping inline
instead of calling it — future changes to `change_status` (extra side effects, logging)
won't apply when status is edited via the admin changeform directly.

### 3.5 Theming convention broken in several page CSS files
`staticfiles/css/pages/about.css` uses `var(--...)` 63 times but the (now-orphaned, see
4.4) testimonial/carousel block hardcodes `#5c3d2e`/`#7a5e4d`/`#fff` and a literal
`'Playfair Display'` font instead of theme variables. Same pattern recurs in
`services.css` (also orphaned, see 4.4), `gallery.css`, `my_profile.css`, and inline in
`all_comments.html`. Since `about.css`/`about.html` are already in the current uncommitted
diff, this is a live area of the codebase.

### 3.6 Redundant DB driver pins
`requirements.txt:28-29` lists both `psycopg2==2.9.10` and `psycopg2-binary==2.9.10`;
normally only one is needed.

**Checked, no issue found:** test coverage is broad (15-18 dedicated test modules per
app), terminology hardcoding does not occur (site_config.* used consistently), feature-flag
gating is enforced both client- and server-side, migrations are a single clean leaf with
no risky field-type changes.

---

## 4. Dead code

### 4.1 Unused functions
- `accounts/templatetags/translate_messages.py:7-9` — `translate_messages` filter is
  registered but never `{% load %}`ed or used anywhere.

### 4.2 Unused imports
- `main_app/views.py:9` — `time` (from `datetime`) unused.
- `accounts/models.py:5` — `AbstractUser` unused (`CustomUser` extends
  `AbstractBaseUser`).
- `accounts/forms.py:3` — `authenticate` unused.
- `main_app/management/commands/populate_db.py:1,9` — `os` and `timezone` unused.
- `accounts/managers.py:21-23` — `GlobalUserModel` is looked up via `apps.get_model()`
  but never used; the code below builds `self.model(...)` directly instead.

### 4.3 Unused templates
- `templates/emails/verification_email.html` — dead; active flow uses OTP
  (`emails/otp_email.html`), and `ACCOUNT_EMAIL_VERIFICATION = 'none'` disables allauth's
  own verification email.
- `templates/partials/working_hours.html` — never included; `home.html:139-148`
  reimplements the same markup inline instead.

### 4.4 Orphaned feature: comment carousel (CSS + JS + partial markup all dead together)
`templates/pages/about.html` no longer contains any comment-carousel/comment-form markup,
but still loads `<script src="{% static 'js/comments.js' %}">` (about.html:82), and
`staticfiles/js/comments.js` queries selectors (`.carousel-wrapper`, `.carousel-item`,
`.prev-btn`, `.next-btn`) that no longer exist on the page. Corresponding orphaned CSS in
`staticfiles/css/pages/about.css`: `.certificate`/`.certificate-section` (superseded by
`.credential-item`/`.credentials-group`), `.comment-carousel`, `.carousel-wrapper`,
`.carousel-item` (+hover/pseudo), `.prev-btn`, `.next-btn`, `.comment-form`,
`.name-form-fields`.
*Verified: `about.html` has no carousel/comment-form markup; still loads comments.js.*

### 4.5 Two fully-unused CSS files
- `staticfiles/css/components/cards.css` (22 lines) — no template uses a bare `class="card"`;
  every card uses a page-prefixed class instead.
- `staticfiles/css/pages/services.css` (117 lines) — `services_page.html` defines its own
  `<style>` block (lines 5-137) with `svc-*`-prefixed classes; the external file's
  `.container`/`.cards`/`.card`/`.card-content`/`.card-title`/`.card-description`/
  `.card-btn` are all orphaned. (Note: that inline `<style>` block also hardcodes hex
  colors rather than using theme variables — same category as 3.5, not separately counted.)
*Verified: no `class="card"` anywhere in templates/; services_page.html confirmed to have
its own inline style block with svc-* classes.*

### 4.6 Other orphaned CSS selectors (files otherwise in use)
- `auth.css`: `.verification-actions` (+ nested `.btn`).
- `home.css`: `.hero-section`/`.hero-content` (lines ~794-868, stale comment claims
  `reservation.html` uses it — it actually uses `.book-page__head`), `.hp-container-prose`,
  `.hp-modal-input`.
- `reservation.css`: `.bn-unauth` (+ variants, lines 556-580).
- `gallery.css`: `.gal-cta` (+ variants, lines 185-203).
- `components/buttons.css`: `.btn-accent` (+hover), `.btn-sm`.
- `layout/grid.css`: `.col-3`, `.col-4`, `.col-6`.
- `layout/header.css`: `.logo-svg--light`, `.logo-text--light` (`.logo-text` itself is
  Django-commented-out in `header.html:7`).
- `detail_page.css`: `.blog-btn` (+hover), `.blog-short-description` (+ responsive
  variants).
- Minor: `styles.css` `@import`s `base/responsive.css` twice.

### 4.7 Possibly-unused model field (verify before removing)
- `accounts.CustomUser.count_messages` (`accounts/models.py:58`) — only appears in the
  admin fieldset; nothing in views/forms/signals/templates reads or increments it.

### 4.8 Commented-out code
- `templates/partials/header.html:7` — single commented-out `<p class="logo-text">` line.
  No other multi-line commented-out blocks found outside migrations.

**Checked, nothing found:** no unused settings, no unused URL patterns (every named route
has a reverse()/`{% url %}` reference).

---

## Suggested next step

Nothing here has been fixed. If you want to act on this, the highest-value, lowest-risk
first pass would likely be: 1.1/1.2 (booking-integrity bugs) → 2.1/2.5/2.7 (share one
`select_related` + index fix) → 4.4/4.5 (delete confirmed-dead CSS/JS) → 3.5 (theming
convention on the files touched in 4.4/4.5 anyway). This is a suggestion, not a plan —
each item would need its own scoped plan before touching code.

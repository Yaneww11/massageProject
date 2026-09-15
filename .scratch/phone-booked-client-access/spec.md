# Spec: Tell phone-booked clients how to reach their reservation

Status: done

## Problem

A client whose Reservation was created **by staff in Django admin** (i.e. they
booked over the phone) has a reservation and no account. Today, if they come to
the site to look it up, they are redirected to a bare login modal with **zero
explanatory text**, and nothing tells them the one thing that matters: their
reservation is bound to the phone number it was booked under.

## What the investigation established

**There is no anonymous self-service booking.** Login is hard-required at three
independent layers, so this is *not* about guest checkout:

- `ReservationPage(BookingEnabledMixin, LoginRequiredMixin, CreateView)`
  (`views.py:155`). Even `check_availability` is `@login_required`
  (`views.py:44-45`).
- `ReservationBaseForm` has no `user` field (`forms.py:64-67`); the owner is
  stamped from the session (`views.py:214-215`).
- `Reservation.user` is a **non-nullable FK** (`models.py:347-351`) — a guest
  reservation is not representable.

**The affected population is real, and arrives a different way.** Staff creating
a reservation in admin creates a **passwordless `CustomUser`**. The client later
*claims* that record by registering with the same phone —
`massageProject/accounts/forms.py:29-58`, `PhoneClaimFormMixin`:

> "If a phone number already belongs to a passwordless (e.g. staff-created) user
> record, attach that record as self.instance so saving the form
> updates/'claims' it"

**The dead end is exactly one page.** `LOGIN_URL` is unset in settings, so
Django's default `/accounts/login/` applies, which maps to `AuthEntryView`
(`accounts/urls.py:13`) rendering `templates/registration/auth_entry.html` — 11
lines: a `<noscript>` plus a script that auto-opens the auth modal. Its own
docstring confirms it is the landing point for every `@login_required` redirect.

**No comparable copy exists.** Neither `.po` file has any message about creating
an account to see bookings. The nearest neighbour is an *error*
(`"Този телефонен номер вече е регистриран..."`, `accounts/forms.py:36`), not an
invitation.

**There is no reservation code.** `Reservation` has no code/token/uuid field;
lookups are by integer `pk`. The "кодове за резервация" phrase in CLAUDE.md
traces to a single `help_text` string on `HomePage.brand_name`
(`models.py:912`) describing where the brand name appears — not a feature. The
only code emails are auth OTPs.

## Decisions

| # | Decision | Rationale |
|---|---|---|
| C1 | Audience is **phone-booked clients with a staff-created passwordless record** | The only population that fits; guest checkout does not exist |
| C2 | The message appears **only on a denied-access redirect**, not on every login | It is an explanation for people who were turned away, not a global banner |
| C3 | Deliver it **inside the auth modal**, via a new optional `note` param on `AuthModal.open()` | `auth_entry.html` auto-opens the modal, so copy placed on that page renders *behind* `.auth-modal-overlay` (`rgba(0,0,0,.45)`, pointer-events blocked) — visible-ish but dimmed and unreadable. Same failure mode as the mobile-login bug |
| C4 | The copy **must name the phone-number constraint** | Claiming only works when registering with the number the booking was made under. Register with a different number and the client silently gets a fresh empty account and the "Нямате предстоящи резервации" empty state, with no explanation. Copy without this clause actively leads people into a trap |
| C5 | msgid authored in **Bulgarian**; English goes in `locale/en` | Project-wide convention — every msgid is BG, `locale/bg` msgstrs repeat the msgid |
| C6 | Phone comes from `business_info.phone`, never hardcoded | `models.py:241-248`, plain CharField (not one of the JSONFields). `context_processors.py:43-52` injects `business_info` into every request, so no view change is needed |
| C7 | `BusinessInfo.phone` becomes **required** (`blank=False`) | Chosen over degrading the copy when the phone is empty |

## Approved copy

Bulgarian (msgid), via `{% blocktrans %}` since `{phone}` is interpolated:

> Резервациите ви са свързани с телефонния номер, с който сте ги направили.
> Създайте профил с този номер, за да ги видите, или ни се обадете на {phone}.

English (`locale/en`):

> Your bookings are linked to the phone number you made them with. Create an
> account with that number to see them, or call us on {phone}.

Rationale for this phrasing over a shorter one: it gives the *reason* before the
instruction, which is what stops someone registering with the wrong number (C4).

## Work

1. **`templates/partials/auth_modal.html`** — accept an optional `note` in
   `open(opts)` (`auth_modal.html:178-195`) and render it inside the modal card
   above the `email` step. Clear it on `close()` so it does not leak into an
   ordinary login opened later on the same page.
2. **`templates/registration/auth_entry.html`** — pass the note when opening:
   `window.AuthModal.open({ next: "...", note: "..." })`, with the copy wrapped
   in `{% blocktrans with phone=business_info.phone %}`.
3. **`massageProject/main_app/models.py:241-248`** — `BusinessInfo.phone`:
   `blank=True` -> required. Update its `help_text` per CLAUDE.md to note the new
   frontend location (it currently says profile page + footer; it will now also
   appear in the login prompt).
4. **Migration** for the field change.
5. **Translations** — `makemessages -l bg -l en`, add the English msgstr,
   `compilemessages`. Per CLAUDE.md.

### Migration caveat (must be handled at deploy)

`blank=False` is a **form-level** constraint — it does not alter the DB column or
backfill anything. An existing `BusinessInfo` row with `phone=''` keeps that
value until someone opens and saves it in admin, and until then the message
renders as "...или ни се обадете на ." Check the production row's `phone` as part
of this deploy, or the copy ships broken on an existing install.

## Out of scope

- **`reservation.html` promises a confirmation that is never sent.** The booking
  panel says *"Потвърждение ще получите на [contact]"* (`reservation.html:264-266`,
  repeated at `:137`), but `emails.py` defines only the three gallery emails and
  there is no reservation post-save signal or confirmation template. Filed as
  `issues/01-missing-booking-confirmation-email.md` — a real defect, but a
  feature to build rather than copy to write.
- **Guest reservation lookup by code/phone.** Would require a
  `Reservation` token field and a public view. Not needed for C1's audience,
  who have a claimable account already.

## Verification

1. Logged out, hit a protected page (`/profile/`) -> redirected to
   `/accounts/login/`; the modal opens with the note visible and legible above
   the email field.
2. Open the login modal normally (header Вход) -> **no** note shown.
3. Open the denied-access modal, close it, open it again from the header on the
   same page -> note does not persist.
4. The rendered phone matches `BusinessInfo.phone` and changing it in admin
   changes the message.
5. Saving `BusinessInfo` in admin with an empty phone is rejected.
6. Switch to EN -> English copy renders; BG -> Bulgarian.
7. `python manage.py test` still green.

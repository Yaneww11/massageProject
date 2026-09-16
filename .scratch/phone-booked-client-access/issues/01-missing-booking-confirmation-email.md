# Booking confirmation is promised but never sent

Status: needs-triage

## Problem

After booking, the confirmation panel tells the client a confirmation is on its
way:

- `templates/pages/reservation.html:264-266`
  `{% trans "Потвърждение ще получите на" %} <strong id="conf-contact"></strong>`
- `templates/pages/reservation.html:137` repeats the promise.

The contact is filled from `views.py:213-235`, which returns
`'contact': str(self.request.user.email or self.request.user.phone_number)`.

**No such email is ever sent.** `massageProject/main_app/emails.py` defines only
`send_gallery_ready_email` (:41), `send_marks_finalized_email` (:51) and
`send_final_delivery_email` (:66) — all photographer-mode gallery emails.
`main_app/signals.py` has no reservation post-save handler, and there is no
`templates/emails/reservation_confirmation*` template.

## Why it matters

The confirmation panel is transient — it is a hidden div revealed client-side
(`reservation.html:679`). Refresh the page and it is gone. The **only**
surviving surface for booking details is the logged-in profile page. A client
who takes the promise at face value and waits for an email gets nothing.

## Open questions

- Email, SMS, or both? The client may have registered by phone with no email.
- Should it also cover status changes (cancelled, rescheduled), or only creation?
- Does it belong in `emails.py` + a `post_save` signal, or explicitly in
  `ReservationPage.form_valid`? Note that `Reservation.save()` calls
  `full_clean()`, and admin-created reservations would also fire a signal —
  decide whether staff-created bookings should email the client too.

## Related

Discovered while specifying `.scratch/phone-booked-client-access/spec.md`.

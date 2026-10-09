# 04: Mark finals delivered by hand from the reservations table

**Spec:** `../spec.md` (Decision 9; Behaviour section "Reservations table").

**What to build:** A "Маркирай като предадени" button in each row of `specialist_reservations_table.html`.

- **When it shows:** proofing is finalized and the reservation isn't delivered, whether or not the client has an email.
- **Click:** opens a confirmation dialog in the page (not a browser `confirm()`). Follow the existing modal pattern, and keep it working with the table's AJAX pagination.
- **Confirm:** POSTs to a new `mark_finals_delivered` endpoint (reservation id).
- **Endpoint:**
  - allows only the assigned specialist or staff, and is photographer-mode gated;
  - accepts POST only;
  - stamps `finals_delivered_at = now()` and saves through `full_clean()`, so `clean()` rejects it when proofing isn't finalized;
  - sends no email;
  - redirects back to the table, keeping the current page and filters.
- **No undo** in the frontend; clearing happens in the admin, as covered by ticket 02.
- **Translations:** run `makemessages`, fill both `.po` files, then run `compilemessages`.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] The assigned specialist and staff can mark a reservation delivered. `finals_delivered_at` is set and no email is sent.
- [ ] Another specialist or the client gets 403/404, and GET is not allowed.
- [ ] With proofing not finalized, the request fails validation and nothing is stamped.
- [ ] After the redirect, the table keeps its page and filters, and the row no longer shows "Маркирай като предадени". (If ticket 03 is done, it shows "Изпрати отново" instead, unless the client has no email.)
- [ ] Translations are compiled, and `python manage.py test` has no new failures.

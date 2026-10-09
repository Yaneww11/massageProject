# 03: Upload a finals ZIP and email it to the client as an attachment

**Spec:** `../spec.md` (Decisions 1–7; Behaviour sections "Finals upload page", "Delivery email", "Reservations table").

**What to build:** A plain Django form view at the `final_gallery_upload` name and URL (the same URL as before; ticket 02 removed it). It has no chunked steps.

- **Access:** the reservation's assigned specialist, or staff. It is photographer-mode gated.
- **Eligible reservations:** `proofing_finalized_at` is set and the client has an email. Already-delivered reservations count as re-sends. The reservation is preselected via the query string.
- **Form:** one file input, `accept=".zip,application/zip"`. Help text states the `FINAL_ZIP_MAX_MB` (a new setting, 15) limit and says "ZIP your edited files without converting them". The browser checks extension and size before submitting.
- **Server-side order:**
  1. Check access, then eligibility. With no client email, refuse with a message pointing to manual delivery.
  2. Check size ≤ `FINAL_ZIP_MAX_MB`.
  3. Validate the ZIP: it opens, `testzip()` finds nothing corrupt, it has at least one file, and every file is an image by extension (`jpg`, `jpeg`, `png`, `tif`, `tiff`, `webp`, `heic`, `dng`, raw). Ignore directories, `__MACOSX/` and `.DS_Store`.
  4. Send the email.
  5. If `finals_delivered_at` is null, stamp it. Redirect to the reservations table with a success message.
  6. Any failure: re-render with an error. Nothing is stamped or stored.
- **No storage:** the upload is never written to storage and no `Gallery`/`Image` is created. Close it in a `finally` block.
- **Email:** `send_final_delivery_email(reservation, zip_file)` attaches the bytes unchanged as `final-photos-reservation-<id>.zip` (`application/zip`) and drops `download_url`. Update the `final_delivery_email` `.html`, `.txt` and subject templates from "download here" to "your final photos are attached", and remove the button.
- **Table (`specialist_reservations_table.html`):**
  - "Качи финали" when proofing is finalized and the reservation isn't delivered;
  - "Изпрати отново" on delivered rows;
  - both hidden when the client has no email.
- **Translations:** run `makemessages`, fill both `.po` files, then run `compilemessages`.

**Blocked by:** 01, 02

**Status:** ready-for-agent

- [ ] Happy path: one email with one attachment named `final-photos-reservation-<id>.zip`, whose bytes equal the upload. `finals_delivered_at` is stamped. No `Gallery`/`Image` rows are created and nothing is written to storage.
- [ ] Re-send to a delivered reservation (by email or by hand): the email is sent and `finals_delivered_at` is unchanged.
- [ ] Each of these is rejected with an error, no email and no stamp:
  - over 15 MB;
  - not a ZIP;
  - a corrupt ZIP;
  - an empty ZIP;
  - a non-image file inside;
  - a client with no email;
  - proofing not finalized.
- [ ] `__MACOSX/` and `.DS_Store` entries are ignored.
- [ ] If the backend raises during sending, an error is shown and nothing is stamped.
- [ ] Access: another specialist or the client gets 403/404, staff are allowed, and the page is inert when photographer mode is off.
- [ ] The table shows the right buttons for undelivered, delivered and no-email rows.
- [ ] Manual check: a 14 MB ZIP sent through the real Gmail backend arrives intact in a Gmail inbox and in one non-Gmail inbox.
- [ ] Translations are compiled, and `python manage.py test` has no new failures.

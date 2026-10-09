Status: ready-for-agent

# Final photos delivered as a ZIP email attachment

## Problem

Final photos are currently uploaded image by image into a `Gallery(gallery_type='final')`. Each image is re-encoded to 2560px WebP at quality 80 (lossy) and stored in GCS. The client is emailed a link to an in-memory ZIP that Django builds on every download. This means:

- the client never gets the photographer's originals;
- every delivery keeps files in the bucket indefinitely;
- the download view builds the whole ZIP in RAM, within a single request that has a 60-second timeout.

Typical final deliveries are under 15 MB. The site owner wants finals to go to the client only as a ZIP attachment on the delivery email, with nothing stored in GCS or on the server.

## Glossary

- **Finals ZIP**: a `.zip` the specialist builds and uploads. It is attached to the email byte for byte, with no re-encoding.
- **Delivered**: `Reservation.finals_delivered_at` is set. This is the only stored trace of finals delivery.
- **Manual delivery**: a staff member or specialist marks a reservation delivered without sending a ZIP, for example when the photos were handed over in person.

## Current state (what the investigation established)

- **Upload:** `FinalGalleryUploadView` (`views.py`, subclass of `GalleryUploadBaseView`) uses the chunked `create|chunk|publish|discard` protocol and `staticfiles/js/chunked-gallery-upload.js`. The template is `templates/pages/final_gallery_upload.html`.
- **Client download:** `download_final_gallery` and `serve_final_gallery_image` (`views.py`, routes in `urls.py`). The "Финални снимки" button is in `templates/pages/my_profile.html`.
- **Model:**
  - `Reservation.final_gallery` is a OneToOne to `Gallery`.
  - `Gallery.TYPE_FINAL`, the `final` subfolder and `IMAGE_CAPS['final']` support it.
  - `Image.clean()` skips the minimum-dimension check for finals (per ADR 0004).
- **Phases:** `PHASE_FINALS_READY` means the gallery exists but no email went out. `PHASE_FINALS_DELIVERED` means `final_gallery` and `finals_delivered_at` are both set.
- **`Reservation.clean()` invariants:**
  - `final_gallery` requires finalized proofing.
  - `finals_delivered_at` requires `final_gallery`.
- **Email:**
  - `send_final_delivery_email` (`emails.py`) sends a link and stamps `finals_delivered_at` when the send succeeds.
  - It sends synchronously through `GmailBackend` (Gmail API).
- **`GmailBackend._send`** (`accounts/email_backend.py`) puts the base64 `raw` message in the JSON request body. Google documents no size limit for that route, and an attachment of about 18 MB would likely get a 413. The upload endpoint (`media_body`, `message/rfc822`) accepts messages up to 35 MB.
- **Receiving limit:** Gmail and many other recipients accept at most 25 MB per message, after base64 encoding. Base64 adds about 33%.

## Decisions

1. **No storage.** The ZIP passes through Django only for the upload request: Django's temp upload file, then the email, then discarded. It has no model, no `FileField` and no GCS object.
2. **Size cap is 15 MB.** That's about 20.5 MB once encoded, leaving margin under the 25 MB receiving limit. It lives in the Django setting `FINAL_ZIP_MAX_MB = 15`, not in `SiteConfiguration`. It is checked in the browser before submitting and again on the server. Anything larger is rejected with a clear message. Nothing is split and there is no link fallback.
3. **The specialist builds the ZIP.** The upload accepts exactly one `.zip` file, and the server never builds or recompresses a ZIP.
4. **The email is sent synchronously,** in the same request as the upload. If the send fails, show the error and change nothing; the specialist retries.
5. **Re-sending is allowed.** A reservation that is already delivered, by email or by hand, can be sent a ZIP again. A re-send keeps the original `finals_delivered_at`.
6. **ZIP validation before sending:**
   - it opens as a ZIP;
   - `testzip()` finds no corrupt member;
   - it has at least one file;
   - every file is an image by extension (`jpg`, `jpeg`, `png`, `tif`, `tiff`, `webp`, `heic`, `dng`, raw formats). Directory entries and `__MACOSX/` / `.DS_Store` junk are ignored.
7. **A client with no email cannot be sent a ZIP.** The form refuses with a message pointing to manual delivery.
8. **Only `finals_delivered_at` is stored.** There is no `finals_delivered_by` and no delivery method.
9. **Manually marking delivered:**
   - **Profile page:** a "Маркирай като предадени" button with confirmation. It is available to the reservation's assigned specialist and to staff, and sends no email.
   - **Admin:** `finals_delivered_at` stays an editable field on the change form, so it can be set or cleared there. Validation comes from `clean()`. There is no admin list action.
   - **Undo:** only by clearing the field in the admin.
10. **The old finals logic is deleted, for finals only.** Proofing (`Gallery`/`Image`, `GalleryUploadBaseView`, chunked JS, WebP) is untouched wherever proofing still uses it.
11. **Existing final galleries are purged,** by a management command run before the migration that drops `Reservation.final_gallery`. Existing `finals_delivered_at` stamps are kept. A reservation in `finals_ready` (gallery stored but never emailed) loses its gallery and shows as "upload finals" again.
12. **The phase model is simplified.** `PHASE_FINALS_READY` is removed, and `finals_delivered` means `finals_delivered_at` is set.
13. **`GmailBackend` sends through the upload endpoint** (`MediaIoBaseUpload(..., mimetype='message/rfc822', resumable=True)`) for every email, so messages up to 35 MB are accepted.

## Behaviour

### Model / migration

- Remove `Reservation.final_gallery`.
- Remove `Gallery.TYPE_FINAL` and its choice, the `final` entry in `RESERVATION_SUBFOLDERS`, and `IMAGE_CAPS['final']`.
- Remove the finals branch in `Image.clean()`, so all galleries get the minimum-dimension and `crop_position` rules again.
- `Reservation.clean()`:
  - drop both `final_gallery` invariants;
  - add: `finals_delivered_at` requires `proofing_finalized_at`.
- Remove `PHASE_FINALS_READY` from the constants, `phase`, `phase_query` and any filter dropdown. `PHASE_FINALS_DELIVERED` becomes `finals_delivered_at IS NOT NULL`.
- Schema migration, in order:
  1. A `RunPython` guard aborts with a clear message if any `Gallery` with `gallery_type='final'` still exists ("run `purge_final_galleries` first").
  2. Drop `final_gallery`.
  3. Alter the `gallery_type` choices.
- `finals_delivered_at` keeps its existing field. Its `help_text` is updated to describe manual set/clear and the client profile line.

### Management command `purge_final_galleries`

- Deletes every `Gallery(gallery_type='final')` with its images. The GCS objects are removed by the existing `pre_delete` signals.
- `--dry-run` prints the count and the reservation ids/phases affected, then deletes nothing.
- It reports how many `finals_ready` reservations (gallery stored, never emailed) lose their files.
- Runs once per deployment, before `migrate`. It is not a cron job.

### `GmailBackend._send`

- Sends the MIME bytes (`message().as_bytes()`) through `media_body=MediaIoBaseUpload(BytesIO(...), mimetype='message/rfc822', resumable=True)` with `body={}`.
- Drops the base64 `raw` encoding.
- Everything else (error handling, `fail_silently`) is unchanged.

### Finals upload page (replaces `FinalGalleryUploadView` and its template)

- **Route:** the same name and URL (`final_gallery_upload`) so the existing table link keeps working. It is a plain Django form view with no chunked steps.
- **Access:** the reservation's assigned specialist, or staff. It is photographer-mode gated like today.
- **Eligible reservations:** `proofing_finalized_at` is set, whether or not the reservation is delivered (delivered ones count as re-sends), and the client has an email. The reservation is preselected via the query string, as today.
- **Form fields:** the reservation, and one file input with `accept=".zip,application/zip"`. The help text states the 15 MB limit and says "ZIP your edited files without converting them".
- **In the browser:** file extension and size are checked before submitting, with an inline error and no request sent.
- **On submit:**
  1. Check access, then eligibility (client email required).
  2. Check size ≤ `FINAL_ZIP_MAX_MB`, then validate the ZIP (Decision 6).
  3. Build the delivery email with the ZIP attached as `final-photos-reservation-<id>.zip` (`application/zip`) and send it.
  4. On success: if `finals_delivered_at` is null, stamp `now()`; otherwise leave it. Show a success message and redirect back to the reservations table.
  5. On failure (validation or send): re-render with an error. Nothing is stamped or stored.
- **Temp file:** the uploaded file is closed and discarded in a `finally` block. Django removes it at the end of the request; no copy is ever made to storage.

### Delivery email

- `send_final_delivery_email(reservation, zip_file)`:
  - attaches the ZIP;
  - drops `download_url` from the context;
  - stamps `finals_delivered_at` only if it is null.
- The `final_delivery_email` templates (`.html`, `.txt`, subject) change from "download here" to "your final photos are attached". The download button is removed.

### Reservations table (`specialist_reservations_table.html`)

- **"Качи финали":** shown when proofing is finalized and the reservation isn't delivered.
- **"Изпрати отново":** shown on delivered rows. It links to the same upload page with the reservation preselected.
- **"Маркирай като предадени":** shown when proofing is finalized and the reservation isn't delivered.
  - It opens a confirmation dialog in the page, not a browser `confirm()`.
  - It sends a POST to a new endpoint (`mark_finals_delivered`, reservation id). The endpoint is restricted to the assigned specialist or staff, stamps `now()`, saves through `full_clean()`, and sends no email.
  - The page then redirects back to the table, keeping the current page and filters.
- When the client has no email, "Качи финали" and "Изпрати отново" are hidden; "Маркирай като предадени" still shows.

### Client profile (`my_profile.html`)

- Remove the "Финални снимки" download button.
- When `finals_delivered_at` is set, show "Финалните снимки са предадени на <date>". This replaces the button, under the same photographer-mode gating.

### Deleted

- `download_final_gallery`, `serve_final_gallery_image` and their URLs.
- `_get_owned_final_gallery_reservation`.
- `_zip_images_response` is **not** deleted; the Marked Photos ZIP still uses it.
- The finals-only branches in `GalleryUploadBaseView` and `chunked-gallery-upload.js`, if any.
- `FinalGalleryUploadForm`.
- The finals fieldset parts in the admin that refer to `final_gallery`. The `finals_delivered_at` field stays.
- The finals tests (`tests/proofing/test_final_gallery.py`, `test_final_gallery_delivery.py`) are rewritten for the new flow.
- Report any dead code this leaves behind; don't remove it silently.

### Docs

- A new ADR, 0005, supersedes the finals part of ADR 0004.
- In `.scratch/specialist-profile-photo-workflow/spec.md`, user stories 19–21 and the "Final Gallery upload + delivery" section are marked superseded, with a link to this spec.

### Translations and help text

- New strings: upload page, validation errors, table buttons, confirmation dialog, profile line, email. Run `makemessages -l bg -l en`, fill both `.po` files, then run `compilemessages`.
- Update `help_text` on `finals_delivered_at` to say where it now shows: the client profile line and the reservations table buttons.

## Out of scope

- Proofing galleries, the Marked Photos ZIP and WebP for proofing.
- Detecting bounces. A bounce goes to the Gmail sending inbox; the site never knows about it.
- Splitting large deliveries or offering a link fallback.
- Background or queued sending.
- Recording who delivered, or by which method.

## Test plan (test-first)

- **Upload, happy path:**
  - The email is sent with one attachment, `final-photos-reservation-<id>.zip`, and its bytes match the uploaded ZIP exactly.
  - `finals_delivered_at` is stamped.
  - No `Gallery` or `Image` rows are created, and nothing is written to storage.
- **Re-send:** the email is sent and `finals_delivered_at` is unchanged.
- **Rejected uploads.** Each of these sends no email, stamps nothing and shows an error:
  - over 15 MB;
  - not a ZIP;
  - a corrupt ZIP;
  - an empty ZIP;
  - a ZIP containing a non-image file;
  - a client with no email;
  - proofing not finalized.
- **ZIP junk:** `__MACOSX/` and `.DS_Store` are ignored.
- **Send failure:** the backend raises, an error is shown and nothing is stamped.
- **Access:**
  - another specialist gets 403/404;
  - the client gets 403/404;
  - staff are allowed;
  - with photographer mode off, the page is inert.
- **`mark_finals_delivered`:**
  - the assigned specialist and staff can stamp it;
  - others get 403/404;
  - with proofing not finalized, a validation error and nothing is stamped;
  - GET is not allowed;
  - no email is sent.
- **Admin:** setting `finals_delivered_at` without finalized proofing gives a validation error; clearing it works.
- **Phase:** delivered when `finals_delivered_at` is set; `PHASE_FINALS_READY` no longer exists; the table phase filter works.
- **Client profile:** shows the delivered line and has no download link. The old URLs return 404.
- **`purge_final_galleries`:** `--dry-run` deletes nothing; a real run deletes the galleries and calls the storage delete; the migration guard aborts while any final gallery exists.
- **`GmailBackend`:** with the Gmail service mocked, `send` is called with `media_body` of mimetype `message/rfc822` and with no `raw`. The existing email tests still pass.

## Done when

- [ ] All of the tests above pass, and the full suite has no new failures.
- [ ] `purge_final_galleries --dry-run` runs against a copy of production data, and its output is reviewed.
- [ ] Translations are compiled.
- [ ] ADR 0005 is written and the old spec's sections are marked superseded.
- [ ] A 14 MB ZIP is sent end to end through the real Gmail backend to a Gmail inbox and to one non-Gmail inbox, and arrives intact.

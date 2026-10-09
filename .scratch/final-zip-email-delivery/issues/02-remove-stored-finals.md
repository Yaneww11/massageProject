# 02: Remove stored final galleries and simplify the finals phase

**Spec:** `../spec.md` (Decisions 8, 10–12; Behaviour sections "Model / migration", "Management command `purge_final_galleries`", "Client profile", "Deleted").

**What to build:** Remove every trace of finals stored as a `Gallery`. Proofing must keep working unchanged.

- **Command `purge_final_galleries`:** deletes every `Gallery(gallery_type='final')` with its images. The GCS objects are removed by the existing `pre_delete` signals. `--dry-run` prints the count and the reservation ids/phases, then deletes nothing. The command also reports how many `finals_ready` reservations lose their files.
- **Migration**, in this order:
  1. a `RunPython` guard aborts with "run `purge_final_galleries` first" if any final gallery exists;
  2. drop `Reservation.final_gallery`;
  3. remove the `final` choice from `gallery_type`.
- **Model:**
  - remove `Gallery.TYPE_FINAL`, `RESERVATION_SUBFOLDERS['final']` and `IMAGE_CAPS['final']`;
  - remove the finals branch in `Image.clean()`;
  - in `Reservation.clean()`, replace both `final_gallery` invariants with "`finals_delivered_at` requires `proofing_finalized_at`";
  - remove `PHASE_FINALS_READY` from the constants, `phase`, `phase_query` and the table's phase filter. Delivered becomes `finals_delivered_at IS NOT NULL`.
- **Delete:**
  - `FinalGalleryUploadView`, its template and `FinalGalleryUploadForm`;
  - `download_final_gallery`, `serve_final_gallery_image` and `_get_owned_final_gallery_reservation`, with their URLs;
  - any finals-only branches in `GalleryUploadBaseView` and `chunked-gallery-upload.js`;
  - the `final_gallery` parts of the admin "Финална галерия" fieldset. `finals_delivered_at` stays editable in the admin, with validation from `clean()`.
  - Keep `_zip_images_response`, which Marked Photos uses.
  - Report any dead code left behind; don't delete it silently.
- **Temporary state:** remove the `final_gallery_upload` URL name and the "Качи финали" link in `specialist_reservations_table.html` for now. Ticket 03 brings both back.
- **Client profile (`my_profile.html`):** replace the "Финални снимки" button with "Финалните снимки са предадени на <date>" whenever `finals_delivered_at` is set, under the same photographer-mode gating.
- **Help text:** update it on `finals_delivered_at` to mention the client profile line and that it can be set or cleared by hand in the admin.
- **Tests:** delete or rewrite `tests/proofing/test_final_gallery.py` and `test_final_gallery_delivery.py` to cover this ticket.
- **Translations:** run `makemessages`, fill both `.po` files, then run `compilemessages`.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] `purge_final_galleries --dry-run` deletes nothing and reports the count, ids and how many `finals_ready` reservations are affected.
- [ ] A real run deletes the final galleries and their images, and calls the storage delete.
- [ ] The migration aborts while any final gallery exists, and applies cleanly once none do.
- [ ] Setting `finals_delivered_at` without `proofing_finalized_at` raises a validation error, in the model and in the admin form. Clearing it in the admin works.
- [ ] The phase is "delivered" when `finals_delivered_at` is set, and `PHASE_FINALS_READY` no longer exists anywhere.
- [ ] The client profile shows the delivered line and has no download link. The old download URLs return 404.
- [ ] The proofing upload, review and Marked Photos ZIP tests pass unchanged.
- [ ] Translations are compiled, and `python manage.py test` has no new failures.

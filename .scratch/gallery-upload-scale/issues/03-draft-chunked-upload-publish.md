# 03: Draft galleries, chunked upload, and an explicit publish step

**What to build:** The photographer can upload a large gallery without hitting a
worker timeout, and the client hears about it only when the photographer says so.

The flow becomes three steps. The photographer picks a reservation and any photo
labels, which creates a **draft** gallery — no email, nothing visible to the
client. The browser then posts the selected images to that draft a few at a time,
sequentially, showing a real determinate progress bar ("142 of 400"). When every
image has landed, the photographer presses **Publish**: only then is the gallery
attached to the reservation, marked as needing client review, stamped with a
publish time, and only then does the client email go out — exactly once, however
many chunks it took.

Chunking is client-side. No broker, no second process (ADR-0003 stands). The
chunk size is a Django setting, not a literal, because the measured value was
sized against a contended 2-vCPU box and cannot be validated on a dev machine.

Per-gallery-type caps land here rather than in a later ticket, because enforcing
them against the old single-shot view first would mean writing the same check
twice: 400 images for proofing and final galleries, 50 for album and homepage.
The cap is checked once per chunk against the gallery's existing count, and
exceeding it is a hard validation error — not a silent truncation. The browser
also refuses a selection that would exceed the cap before uploading a single
byte. Do not put the check in per-image validation: that is an extra COUNT per
image, and it would trip mid-batch leaving a partly-filled gallery.

Applies to the two frontend photographer workflows only. The admin bulk action is
ticket 05.

**Blocked by:** 01 (Unify the two gallery upload views onto a shared base).

**Status:** done

- [ ] 400 images upload to a proofing gallery without a worker timeout; the
      gallery ends with exactly 400 images and **one** client email is sent
- [ ] The same flow works for a final gallery, with its own delivery email
- [ ] No email is sent at draft creation or on any chunk — only at publish
- [ ] A draft that is never published is invisible to the client
- [ ] Chunk size is read from a setting; the ticket records that the value still
      needs tuning against prod-equivalent hardware and that a local run does not
      validate it
- [ ] Selecting more images than the gallery type allows is refused in the
      browser before upload starts, and a chunk that would exceed the cap is
      rejected server-side with no partial write
- [ ] New strings are added to both translation catalogs and compiled per
      CLAUDE.md, with no collateral loss of existing translations
- [ ] `python manage.py test` is green

## Notes

Two design gaps the spec did not cover, both resolved during implementation:

- A draft gallery had no owner. `Reservation.gallery` is the OneToOne that
  publish sets, so until publish nothing tied a gallery to a reservation or a
  photographer, and the chunk endpoint had no queryset to authorise against.
  Resolved with a nullable `Gallery.draft_reservation`.
- `(filename, size)` is not recoverable from saved rows: WebP conversion
  rewrites the name to `.webp` and the stored size to the WebP size. Resolved
  by capturing `Image.source_name` / `source_size` before saving.

**Not verified:** the 6-per-chunk figure. The 400-image test uses tiny images
and proves chunking, ordering, capping and resume — not the timing, which was
sized against a contended 2-vCPU box. `GALLERY_UPLOAD_CHUNK_SIZE` is a setting
so it can be retuned on prod without a code change.

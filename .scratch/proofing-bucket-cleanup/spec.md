# Spec: purge unmarked proofs at finalisation + per-reservation bucket folders

Status: implemented (see `01-implementation-log.md`)
Triage: `00-triage.md`

## Decisions taken

| Question | Answer |
| --- | --- |
| Cleanup trigger | Option 1 — purge the **unmarked** proofs when the client finalises |
| Folder shape | Nested per reservation: `reservations/<id>/proofing/`, `reservations/<id>/final/` |
| Existing blobs under `gallery/photos/` | Left alone — new uploads only, no backfill command |
| Already-finalised reservations | Not purged retroactively — going forward only |

## 1. Bucket structure

`Image.image.upload_to` becomes a callable:

- Gallery is `TYPE_PROOFING` and its reservation is known → `reservations/<res_id>/proofing/<filename>`
- Gallery is `TYPE_FINAL` and its reservation is known → `reservations/<res_id>/final/<filename>`
- Anything else (homepage, album, or no reservation link) → `gallery/photos/<filename>` (unchanged)

The reservation id is resolved from the gallery, preferring the published link
(`Gallery.reservations` / `Gallery.final_gallery_reservation`) and falling back to
`draft_reservation_id`, which `_create_draft` (`views.py:565`) always sets for the two
upload views. At first save `instance.pk` is `None` but `instance.gallery` is already
assigned (`views.py:389`, `admin.py:301`), so the gallery is always reachable.

`proof_derivatives/<image_id>/` and `marked_thumbnails/<image_id>.webp` stay where they
are. Keeping them out of the reservation folder is what lets that folder hold nothing
but the client's chosen photos.

A migration records the `AlterField`. It does not move any blob: existing rows keep the
`gallery/photos/...` names already stored in the DB.

## 2. Purge of the unmarked proofs

New `Reservation.purge_unmarked_proofs()`: deletes the `Image` rows of the proofing
gallery that have no `ImageProof` with `is_marked=True`, then stamps
`proofs_purged_at`. Row deletion is the mechanism — the existing `pre_delete` receivers
in `signals.py` remove the original blob and the derivatives. Returns the number of rows
deleted. Idempotent.

### It runs from cron, not from the finalise request

Measured, not assumed: **4.0 storage calls per purged image** (1 `listdir` for the
derivative prefix + 3 deletes). A 400-cap gallery with ~350 unmarked frames is ~1400
sequential calls — around 70 seconds at a 50 ms round trip, minutes at 80 ms. That
outlasts a gunicorn worker timeout, and a timeout is a SIGKILL no `try/except` can
catch: the client would see a 502 on a finalisation that actually succeeded.

A fire-and-forget thread is also out. `gunicorn-watchdog.sh` exists because this host
(SiteGround) kills workers under resource limits, so a thread would lose purges
silently and permanently, with nothing to retry them.

The project already runs cron (`gunicorn-watchdog.sh`, `gunicorn-log-rotate.sh`), so:

- `finalize_photo_proofing` leaves the reservation **purge-pending** — finalised, with
  `proofs_purged_at` still NULL.
- A `purge_unmarked_proofs` management command processes
  `proofing_finalized_at__isnull=False, proofs_purged_at__isnull=True`, one reservation
  at a time so one bad gallery cannot abort the run. A failure leaves the stamp NULL, so
  the next run retries it. `--dry-run` reports without deleting.
- The owner registers the crontab entry host-side.

**Consequence the owner must know: the bucket is clean within one cron interval, not
the instant the client clicks finalise.**

### New field

`Reservation.proofs_purged_at` (nullable datetime, audit/internal — no `help_text`, not
in the admin fieldsets). The migration backfills it to `proofing_finalized_at` for every
already-finalised row, which is how "going forward only" is enforced: the command can
never sweep the pre-existing backlog. Nulling the column is the escape hatch if the
owner later changes their mind about it.

### Consequences, accepted

- `unlock_proofing()` still works, but reopens a gallery containing only the chosen
  photos. The client cannot go back to a frame they didn't pick.
- The `marked` and `all` filter tabs (`views.py:1243`) become the same set once only
  marked images remain. No UI change; the existing `is_finalized` branch already blanks
  the `marked` tab after finalisation.

## 3. Storage-delete fixes

`delete_file_from_gcs` now goes through `default_storage.delete()` instead of a
hand-rolled client. django-storages' `GoogleCloudStorage.delete()` is a single
`delete_blob` on the backend's own cached client and already swallows `NotFound`, which
makes both the client singleton and explicit `NotFound` handling unnecessary. The
`exists()` guard before the thumbnail delete in `_delete_image_derivatives` goes for the
same reason.

This roughly halves the per-image cost. It does **not** make the purge viable in a
request — 4.0 calls per image is the figure *after* this change, which is why §2 moved
it to cron.

Trade-off: a delete of a key that was never there is now indistinguishable from a
successful one. It already was, under `else: pass` — but a real storage error is now
logged and sent to Sentry, which the old code did not do.

## Success criteria

1. An `Image` saved into a proofing gallery whose reservation is known lands under
   `reservations/<id>/proofing/` → assert on `image.image.name`.
2. Same for a final gallery → `reservations/<id>/final/`.
3. A homepage/album image still lands under `gallery/photos/`.
4. `purge_unmarked_proofs()` deletes exactly the unmarked rows, keeps the marked ones,
   and removes the unmarked originals and their derivatives from storage.
5. Run twice, it deletes nothing the second time, and it stamps `proofs_purged_at`.
6. It costs no more than 4 storage calls per purged photo — asserted, since this is the
   number that forced the purge off the request path.
7. Finalising leaves the reservation purge-pending and deletes nothing; the command then
   purges it.
8. The command skips unfinalised and already-stamped reservations, and one failing
   reservation neither aborts the run nor loses its place in the queue.
9. Full suite shows no new failures against the 12 known pre-existing ones.

No new user-facing strings expected, so no `makemessages` run unless that changes.

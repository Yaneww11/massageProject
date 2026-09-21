# Triage: proofing images stay in the GCS bucket after the client finalises

Status: triaged, awaiting decision
Reported: 2026-09-19 — "after user review and finalised his images they are not deleted from Google Cloud Bucket"

## Diagnosis

**Not a broken delete — nothing ever asks for a delete.** This is a feature gap, not a
silent failure.

`finalize_photo_proofing` (`massageProject/main_app/views.py:1343`) does exactly four
things: reject if already finalised, require ≥1 marked photo, call
`Reservation.finalize_proofing()`, send the photographer an email.
`finalize_proofing()` (`massageProject/main_app/models.py:581`) only stamps
`proofing_finalized_at` and clears `need_client_review`. No `Image` row is deleted, so
no storage delete is ever triggered.

Storage deletion is wired **only** to the `Image` row lifecycle, in
`massageProject/main_app/signals.py`:

- `delete_image_on_model_delete` (`pre_delete`, global) → `delete_file_from_gcs(...)`
  removes the original `gallery/photos/<name>.webp`.
- `clear_proof_derivatives_on_image_delete` (`pre_delete`, `sender=Image`) →
  `_delete_image_derivatives` removes `proof_derivatives/<pk>/*` and
  `marked_thumbnails/<pk>.webp`.

Both fire on cascade too (the global `pre_delete` receiver disables Django's
fast-delete path), so deleting `Image` rows — individually or via a `Gallery` cascade —
does clean the bucket. The only place that happens today is the upload-discard path
(`views.py:685`, `views.py:710`), which throws away an unpublished draft.

### Ruled out

- **Path-prefix mismatch.** `STORAGES["default"]["OPTIONS"]` (`settings.py:229`) sets
  only `bucket_name` and `credentials` — no `location`. So `default_storage`'s keys and
  the raw-client keys in `delete_file_from_gcs` agree; `blob.exists()` is not failing
  on a wrong prefix.
- **`ImageField` name match.** `delete_old_image_on_update` / `delete_image_on_model_delete`
  match on `field.__class__.__name__ == 'ImageField'`. `Image.image` is a plain
  `models.ImageField`; `WebPImageFieldsMixin` (`models.py:39`) only overrides `save()`
  and does not swap the field class. The receivers do see the field.

## Separate finding (real, independent of the above)

`delete_file_from_gcs` (`signals.py:158-162`) ends in:

```python
if blob.exists():
    blob.delete()
else:
    pass
```

A miss is a silent no-op — no log, no Sentry breadcrumb. A delete that never happened
is indistinguishable from one that succeeded, which is precisely why this report needed
a code read instead of a log read. Worth a `logger.warning` regardless of which option
below is chosen.

## Landmine: `Reservation.gallery` is `on_delete=CASCADE`

`Reservation.gallery` (`models.py:385`) and `Reservation.final_gallery`
(`models.py:393`) are both `OneToOneField(..., on_delete=models.CASCADE)`. **Deleting a
published proofing `Gallery` deletes the reservation row with it.** That rules out
"delete the Gallery" as the cleanup mechanism, in code *and* by hand in the Django
admin. Any purge must delete the `Image` rows and leave the `Gallery` standing.

(The discard path is safe only because the draft it deletes is not yet attached to a
reservation.)

## Constraint that shapes the fix

`Reservation.unlock_proofing()` (`models.py:586`) exists and is reversible — the
photographer can reopen a finalised review. **Purging originals at
`proofing_finalized_at` would break unlock**: the client would come back to an empty
gallery. The safe terminal trigger is `finals_delivered_at` (`PHASE_FINALS_DELIVERED`),
not finalisation.

## Options (needs the owner's call)

1. **Purge the unmarked proofs at finalisation.** Delete `Image` rows in the proofing
   gallery with no `ImageProof.is_marked=True`. Frees the bulk of the storage at the
   earliest point — but is destructive and unlock-hostile (the client can no longer
   change their mind about a photo they didn't pick).
2. **Purge the proofing photos once finals are delivered.** When `finals_delivered_at`
   is stamped, delete `reservation.gallery.images.all()` — the rows, **not** the
   `Gallery` (see the landmine above) — and the existing signals clean originals and
   derivatives. Safe with respect to `unlock_proofing`, but the storage is held for the
   whole editing window.
3. **Evict only the derivatives at finalisation.** Drop `proof_derivatives/<pk>/*` and
   `marked_thumbnails/<pk>.webp` while keeping originals. Fully reversible — they are
   regenerated on demand — and reclaims the watermarked-copy duplication, which for a
   multi-client gallery can exceed the originals.

(1) and (2) are mutually exclusive in spirit; (3) composes with either.

## Stopgap for what is already in the bucket

Deleting individual `Image` rows in the Django admin fires the same signals and does
clean the bucket today. Do **not** delete a `Gallery` in the admin to achieve this — the
CASCADE above will take the reservation with it.

## Question back to the owner

- Which of the three is the intended behaviour? "Deleted after review" reads closest to
  (1), but (2) is the one that doesn't fight `unlock_proofing`.
- Is a retention window wanted (e.g. purge N days after delivery) rather than an
  immediate delete?

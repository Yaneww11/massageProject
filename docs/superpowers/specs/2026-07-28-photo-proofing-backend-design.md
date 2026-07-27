# Photo Proofing Gallery — Backend Design

Date: 2026-07-28

## Context

`templates/pages/photo_proofing.html` (view: `PhotoProofingGallery` in
`massageProject/main_app/views.py`) is a fully designed, fully interactive
proofing page: one-click favorite marking, per-label chips with caps, a
compare-two view, per-photo comments, an All/Marked/Finalized filter, and a
sticky Review & Finalize action. All of that state currently lives only in
client-side JS (`marks`, `labelCounts`, `compareSet`, `comments`, `finalized`)
with no persistence, and photos are served straight from `image.url` with no
protection.

This spec covers making that real:

1. Persist marks, labels, and comments server-side.
2. Once the client finalizes, the gallery becomes read-only; only an admin
   can unlock it (state is preserved on unlock, not reset).
3. Real image protection: capped, per-user-watermarked derivatives served
   through short-lived signed URLs, with a Referer check as a deterrent
   against hotlinking.

The project is mid-migration to Google Cloud Storage as the default file
storage backend (`storages.backends.gcloud.GoogleCloudStorage`, wired in an
uncommitted `settings.py`/`signals.py`/`requirements.txt` change already in
the working tree). This design is written against Django's storage
abstraction (`default_storage`, `ImageField.open()`) rather than any
GCS-specific client code, so it works unchanged on local disk (dev) or GCS
(prod) — the one GCS-specific behavior it relies on is that
`storages.backends.gcloud.GoogleCloudStorage.url(name, expire=seconds)`
returns a real, short-lived v4 signed URL, which is exactly what "signed
expiring URLs" needs.

## Non-goals

- Configuring the GCS bucket/credentials themselves — that's the user's own
  in-progress work, not part of this spec.
- Making the label set/caps global or reusable across galleries — each
  gallery has its own `PhotoLabel` rows (per earlier decision).
- Preventing screenshots — explicitly out of scope per the original design;
  the watermark exists so a captured frame is traceable, not to prevent
  capture.
- A frontend-visible admin unlock control — unlock is a Django admin action
  only.
- Changing anything about the existing homepage/album gallery pages — this
  only touches the reservation-proofing path.

## Data model

### `Reservation` (add fields + methods)

```python
proofing_finalized_at = models.DateTimeField(null=True, blank=True)
proofing_finalized_by = models.ForeignKey(
    'accounts.CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
)
```

Mirrors the existing `status_updated_at`/`status_updated_by` audit pair.
Two methods, mirroring `change_status()`:

```python
def finalize_proofing(self, user):
    self.proofing_finalized_at = timezone.now()
    self.proofing_finalized_by = user
    self.save(update_fields=['proofing_finalized_at', 'proofing_finalized_by'])

def unlock_proofing(self):
    self.proofing_finalized_at = None
    self.proofing_finalized_by = None
    self.save(update_fields=['proofing_finalized_at', 'proofing_finalized_by'])
```

`is_proofing_finalized` becomes a small `@property` returning
`self.proofing_finalized_at is not None`, used by the view and templates.

### `PhotoLabel` (new model)

```python
class PhotoLabel(models.Model):
    gallery = models.ForeignKey(Gallery, on_delete=models.CASCADE, related_name='photo_labels')
    name = models.CharField(max_length=100, help_text=_(
        'Името на етикета, който клиентът вижда и може да прикачи към снимки '
        'при преглед на снимките от резервацията си.'
    ))
    cap = models.PositiveIntegerField(validators=[MinValueValidator(1)], help_text=_(
        'Максимален брой снимки, които клиентът може да маркира с този етикет '
        'при преглед на снимките от резервацията си.'
    ))
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']
        verbose_name = _('Етикет за преглед на снимки')
        verbose_name_plural = _('Етикети за преглед на снимки')

    def __str__(self):
        return self.name
```

Admin-managed per gallery via a `TabularInline` on `GalleryAdmin`, next to
the existing `ImageInline`.

### `ImageProof` (new model — per-photo client state)

```python
class ImageProof(models.Model):
    image = models.OneToOneField(Image, on_delete=models.CASCADE, related_name='proof')
    is_marked = models.BooleanField(default=False)
    comment = models.TextField(blank=True, default='')
    labels = models.ManyToManyField(PhotoLabel, blank=True, related_name='images')
    updated_at = models.DateTimeField(auto_now=True)
```

Created lazily (`get_or_create`) the first time a photo is marked, labeled,
or commented on — most photos in a gallery will never get a row, which is
fine (`Image` proofing views treat a missing `ImageProof` as "not marked, no
labels, no comment").

### Migration

One migration adding the two `Reservation` fields, the `PhotoLabel` model,
and the `ImageProof` model. No data migration needed (new fields
default/null, no existing rows to backfill).

## Views & endpoints

All new endpoints live in `massageProject/main_app/views.py`, function-based
with `@login_required`, matching the existing `submit_comment` pattern, and
registered in `urls.py` under `profile/photos/...`. Every mutating endpoint:

- 404s if the `image_id` doesn't belong to a gallery attached to a
  reservation owned by `request.user` (no leaking existence of other users'
  photos via id guessing).
- Returns 403 with a JSON error if `reservation.is_proofing_finalized`.
- Returns JSON (`{'success': True, ...}` / `{'success': False, 'error': ...}`)
  matching `submit_comment`'s response shape, so the frontend JS can show an
  error and roll back its optimistic UI update on failure.

| Endpoint | Method | Behavior |
|---|---|---|
| `/profile/photos/<image_id>/mark/` | POST | Toggle `ImageProof.is_marked`. |
| `/profile/photos/<image_id>/label/<label_id>/` | POST | Toggle the label on/off. Rejects with 400 if turning it on would exceed `PhotoLabel.cap` (counts current `ImageProof` rows with that label, across the same gallery). |
| `/profile/photos/<image_id>/comment/` | POST | Set/overwrite `ImageProof.comment` from `request.POST['content']` (same 2000-char cap as `submit_comment`). |
| `/profile/photos/finalize/` | POST | Resolves the user's active proofing reservation (same lookup `PhotoProofingGallery.get_context_data` already does), 400s if zero photos are marked, otherwise calls `reservation.finalize_proofing(request.user)`. |

`PhotoProofingGallery.get_context_data` gains:

- `context['is_finalized'] = reservation.is_proofing_finalized if reservation else False`
- Per-photo `is_marked`/`comment`/`label_keys` merged into each photo dict
  from `ImageProof` (a single `select_related`/`prefetch_related` query, not
  N+1).
- `context['labels_config']` now built from `reservation.gallery.photo_labels.all()`
  instead of the hardcoded Python list — falls back to the same hardcoded
  three (за печат/album/social) only in the `is_demo` (no real gallery) case,
  so the placeholder experience is unchanged.

## Read-only enforcement

Server-side, not just JS:

- The mutating endpoints above already 403 once finalized.
- `photo_proofing.html`'s template renders every interactive control
  (mark/compare/label/comment buttons) with `disabled` when
  `is_finalized` is true, and the finalize button/modal are hidden — the
  existing JS `finalized` flag becomes `{{ is_finalized|yesno:"true,false" }}`
  at init instead of always starting `false`, so a page reload after
  finalizing lands already-locked, no JS round-trip needed to find out.
- This is defense in depth: even if someone bypasses the JS entirely, the
  view-level 403 is what actually enforces the lock.

## Admin unlock

- New `@admin.action` on `ReservationAdmin`, alongside the existing
  `mark_as_completed`/`mark_as_noshow`: `unlock_photo_proofing`, calling
  `reservation.unlock_proofing()` for each selected row where
  `proofing_finalized_at` is set (silently skips rows that aren't
  finalized).
- `proofing_finalized_at`/`proofing_finalized_by` added to
  `ReservationAdmin`'s existing "Системен одит" (collapsed) fieldset,
  read-only, next to `status_updated_at`/`status_updated_by`.
- Unlocking does not touch `ImageProof` rows — marks/labels/comments survive
  untouched, matching the earlier decision.

## Image protection pipeline

Two hops:

**1. Our own signed entry view** — `GET /profile/photos/img/<token>/`.
`token` is produced by `django.core.signing.TimestampSigner` (or
`dumps`/`loads` with a salt specific to this feature), encoding
`{'image_id': ..., 'user_id': ...}`. Generated fresh in
`PhotoProofingGallery.get_context_data` for every photo on every page render
(so it's naturally short-lived per visit — no separate expiry bookkeeping
needed beyond the signer's own `max_age` check).

The view:
- Verifies signature and `max_age` (e.g. 6 hours — long enough to cover one
  browsing session, short enough that a stale bookmarked link goes dead).
- Verifies `user_id` matches `request.user.pk` and that
  `Image.objects.get(pk=image_id)`'s gallery belongs to a reservation owned
  by that same user — both checks, not just one, so a signature replay by a
  different logged-in user still fails.
- Checks `HTTP_REFERER`: if present and its host isn't in `ALLOWED_HOSTS`,
  reject with 403. Missing `Referer` is allowed (browsers routinely omit it;
  over-blocking here would break normal direct navigation).
- Ensures a derivative exists at storage path
  `proof_derivatives/{image_id}/{user_id}.jpg` — generates it if not:
  reads the original via `image.image.open('rb')`, uses Pillow to downscale
  to a capped long edge (1600px) and draw a repeating diagonal watermark
  containing the same `watermark_identifier` string already shown in the
  CSS overlay today, saves the JPEG via `default_storage.save(path, ContentFile(...))`.
  This uses only the storage abstraction — no code here knows or cares
  whether it's writing to local disk or GCS.
- Redirects (302) to `default_storage.url(path, expire=300)` — a 5-minute
  signed URL when storage is GCS (via django-storages' built-in `expire`
  param on its GCS backend), or just the plain local media URL in dev
  (`FileSystemStorage.url()` ignores `expire`, which is fine — local dev
  has no equivalent threat model).

**2. The browser fetches the actual bytes** directly from wherever
`default_storage.url()` pointed — no further Django involvement, so image
bandwidth doesn't run through the app server once storage is GCS.

`templates/pages/photo_proofing.html`'s `<img src="{{ photo.url }}">`
changes to point at this signed entry view instead of `image.image.url`,
for real (non-demo) photos only — the existing SVG data-URI placeholders
for the no-gallery-yet case are untouched (no protection needed for fake
gradients).

The existing right-click/drag-disable JS and CSS watermark overlay stay
exactly as they are today — they're an additional, independent layer on top
of the real baked-in pixel watermark, not replaced by it.

**Derivative cache invalidation**: if an admin replaces a reservation photo
(same `Image` row, new file), the cached derivative(s) under
`proof_derivatives/{image_id}/` would otherwise go stale. Extend the
existing `delete_old_image_on_update` signal in `signals.py` (it already
fires on every `ImageField` change, including `Image.image`) with one more
step specific to the `Image` model: after detecting the file changed,
delete any `default_storage` entries under that image's derivative prefix
so the next view request regenerates them from the new original. This is a
small addition to an existing, already-generic signal handler — not a new
mechanism.

## Frontend JS changes

`photo_proofing.html`'s inline `<script>` swaps its in-memory mock state for
real persistence, keeping the same optimistic-UI feel:

- Mark toggle: flip the UI immediately, `fetch(POST mark-url)` in the
  background; on a non-OK response, revert the UI and show the existing
  error-toast pattern (none exists yet — reuse a simple inline message,
  consistent with how `submit_comment`'s errors are surfaced elsewhere in
  the codebase, e.g. the comment form).
- Label toggle: same optimistic pattern; a 400 (cap exceeded) reverts the
  chip state — this should be rare since the client already disables chips
  at their cap, but the server check is the real guard against a stale
  client or two open tabs.
- Comment save: existing drawer's Save button posts the textarea content;
  same success/failure handling.
- Finalize confirm: posts to the finalize endpoint; on success, sets
  `finalized = true` in JS (as it already does today) — no page reload
  needed, but a later reload will also correctly land in the locked state
  server-side.
- `compareSet` stays pure client-side UI state (never persisted — comparing
  two photos side-by-side isn't something that needs to survive a reload).

## Translations

New user-facing strings this introduces (admin action label, any new error
messages surfaced by the JSON endpoints, `PhotoLabel`/`ImageProof` verbose
names and help text) go through the existing workflow:

```bash
python manage.py makemessages -l bg -l en
# fill in/correct any new msgid entries
python manage.py compilemessages
```

## Testing

- **Model**: `PhotoLabel.cap` enforcement (via the view, since the model
  itself doesn't self-enforce caps — caps are a request-time business rule,
  not a DB constraint), `Reservation.finalize_proofing`/`unlock_proofing`
  state transitions, `ImageProof` lazy-creation.
- **Views**: 404 on non-owner access to another user's image endpoints, 403
  on any mutating endpoint once finalized, 400 on exceeding a label's cap,
  400 on finalizing with zero marks, the admin unlock action clearing the
  two fields and leaving `ImageProof` rows untouched.
- **Image-serving view**: valid token round-trip serves a redirect; expired
  token (mock `TimestampSigner` with `max_age=0`) 403s; token signed for a
  different `user_id` 403s; mismatched cross-origin `Referer` 403s; missing
  `Referer` succeeds; derivative is only generated once (second request
  doesn't reprocess the original — assert on a mocked/counted Pillow call
  or on `default_storage.exists()` before/after).

## Open implementation questions to resolve during coding (not blocking this spec)

None — the per-question decisions from brainstorming (lock trigger, unlock
behavior, comment model shape, label config scope, storage strategy) are
all reflected above.

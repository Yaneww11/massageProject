# Spec: Gallery upload at scale (50–400 images)

Status: triaged — see `issues/`

## Problem

The photographer needs to upload 50–400 images into a Proofing Gallery or Final
Gallery. Today that is impossible, and the client-facing read side would not
survive it either.

### Measured baseline

Per-image cost of the real pipeline (`massageProject/main_app/models.py:39-73`),
median of 5 iterations on an idle 16-core laptop:

| Input | Source JPEG | Total/image | WebP out |
|---|---|---|---|
| 6000x4000 (24MP) | 3.6 MB | **975 ms** | 707 KB |
| 4000x3000 (12MP) | 1.8 MB | **755 ms** | 575 KB |
| 2000x1500 (3MP)  | 0.45 MB | **275 ms** | 246 KB |

The LANCZOS resize + WebP encode is 99.9% of the cost and is strictly
single-threaded (`cpu/wall = 1.00`). Production is a 2-vCPU box with
**2 sync gunicorn workers, 1 thread each, 30 s timeout** (never configured —
gunicorn defaults, see `entrypoint.sh`, `without-docker-deploy.sh:30-36`,
`gunicorn-watchdog.sh:56-62`).

### The three binding ceilings today

1. **Gunicorn 30 s timeout** — the real limit. ~24 images/request at 24MP on a
   fast idle machine; roughly half that on contended prod. This is what breaks.
2. `DATA_UPLOAD_MAX_NUMBER_FILES` = 100 (Django default; no override exists
   anywhere in the project). Never reached, because (1) fires first.
3. Reverse-proxy body cap — SiteGround, not version-controlled here.

400 x 24MP is ~6.5 minutes of pure CPU on the benchmark machine, plausibly
15+ minutes on prod, and ~1.4 GB of upload.

### Read-side problems at the same scale

- `templates/pages/photo_proofing.html:48-88` emits one `<img>` per photo with
  **no `loading="lazy"` and no pagination**. A 400-photo gallery fires 400
  concurrent requests at `serve_proof_image` (`views.py:859-885`), each doing a
  GCS `exists()` and, cold, a full decode + watermark composite + GCS PUT —
  against 2 workers.
- `serve_marked_photo_image` (`views.py:492-499`) streams the **full-size
  2560 px WebP** through a gunicorn worker for every thumbnail on the
  specialist's Marked Photos page. No derivative, no cache, no lazy-loading.
- `default_storage.url(path, expire=300)` (`views.py:879`) is **dead code**: the
  installed GCS backend's signature is `url(self, name, parameters=None)`, so it
  raises `TypeError` on *every* request and falls into a branch whose comment
  claims it is local-dev-only. Watermarked client proofs are therefore served
  with the backend-default **24-hour** signed URL, and a warning is logged each
  time.

## Decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | Scope is the frontend `ProofingGalleryUploadView` (`views.py:356`) and `FinalGalleryUploadView` (`views.py:538`) | These are the real per-reservation workflow |
| D2 | 400 images is a **total per gallery**, reached over many chunked requests | One request carrying 400 conversions cannot fit in 30 s |
| D3 | Caps differ by `gallery_type`: **400** for `proofing`/`final`, **50** for `album`/`homepage` | A 400-slide homepage carousel is a bug, not a feature |
| D4 | Exceeding a cap is a **hard validation error** | A limit that is routinely ignored is not a limit |
| D5 | **Client-side chunking**, not a task queue | No broker, no second process; ADR-0003 (single container, no CI) stands |
| D6 | **6 images per chunk** | ~6 s measured, ~15–18 s on contended prod, inside 30 s with GCS PUT headroom. 400 images ~= 67 chunks |
| D7 | Gunicorn: `--worker-class gthread --threads 4`, `--timeout 60` | Helps the **read** side only, where requests genuinely wait on GCS. Uploads are CPU-bound and GIL-held — threads do not speed them up |
| D8 | Proofing page: `loading="lazy"` + **pagination, 60/page** | Pagination is the only option that bounds the worst case; lazy-loading alone still lets a fast scroll stampede 2 workers |
| D9 | New `Gallery.published_at`; the client email fires only on an explicit publish step | At 10–15 min per upload, a partial gallery is routine. A draft must be findable and resumable |
| D10 | Chunk failure: retry 3x with backoff, then halt and allow resume | Skipping failures silently ships incomplete client galleries — the one outcome that damages the business |
| D11 | Marked Photos gets a new lazily-generated cached ~400 px thumbnail derivative, no watermark | Fixes worker occupancy *and* bandwidth; reuses the caching pattern already in the file |
| D12 | Signed-URL TTL for proofing images: **15 minutes**, via a helper on the proofing path | Global `GS_EXPIRATION` would silently reshape public marketing image URLs too. 300 s is short enough to die mid-session |
| D13 | Admin bulk action (`admin.py:264`) gets the caps but **not** chunking | `album`/`homepage` are curated in admin, so the 50 cap must live there. 400 never happens on that surface |
| D14 | **Superseded by `.scratch/photolabel-cap-removal/spec.md`.** No displayed label count exists — the earlier wording was wrong. The real issue is that client-side *cap bookkeeping* (`labelCounts`, `photo_proofing.html:214-222`) is built by scanning chips **on the current page**, so under D8's pagination a client on page 2 computes caps from 60 photos instead of 400 and chips stop disabling correctly. Task 4 deletes that machinery outright | Keeping the two specs independent was the explicit call; see Sequencing below |

## Out of scope

- `Gallery.photo_count` N+1 (`models.py:753-755`, rendered at `gallery.html:30`
  and `:58`, plus `admin.py:260-262`) — deferred; task 4 may delete that
  rendering entirely.
- `PhotoLabel.cap` removal — owned entirely by
  `.scratch/photolabel-cap-removal/spec.md`.

## Sequencing

These two specs were deliberately kept independently shippable. They touch the
same JS block, so order matters:

- **Task 4 first (preferred):** the cap machinery is gone before pagination
  lands; nothing to reconcile.
- **This spec first:** pagination ships while `labelCounts` is still page-scoped,
  so label chips stop disabling correctly for clients past page 1. They fall back
  to the server-side rejection (`views.py:963`) surfaced as a `window.alert` —
  degraded, not broken, and transient until task 4 lands. Accept knowingly or
  reorder.
- Moving image conversion to a background queue (option B at Q6). Revisit if
  this ever serves more than one photographer.

## Work

### 1. Caps

- Add a per-type cap constant on `Gallery` (400 proofing/final, 50 album/homepage).
- Enforce at the form/view layer, once per chunk:
  `existing_count + len(incoming) > cap` -> `ValidationError`.
  **Not** in `Image.clean()` — that is one extra COUNT per image, and it would
  trip mid-batch leaving a partly-filled gallery.
- Client-side pre-flight: refuse a selection that would exceed the cap *before*
  uploading a single byte.
- Apply the same cap check to the admin bulk action; add a visible
  "upload up to ~20 at a time" note to that form.

### 2. Draft galleries and publishing

- Migration: add `Gallery.published_at` (nullable datetime).
- Split `ProofingGalleryUploadView` / `FinalGalleryUploadView` into three steps:
  1. **create** — `Gallery` + `PhotoLabel`s, returns gallery id. No email.
  2. **chunk** — accepts <= 6 images, appends to the draft. Idempotent on
     (filename, size) so a resumed upload skips what is already there.
  3. **publish** — sets `reservation.gallery` (or `final_gallery`),
     `need_client_review=True`, `published_at`, and **only here** sends
     `send_gallery_ready_email` / `send_final_delivery_email`.
- Photographer can see and resume unpublished drafts.
- **Abandoned drafts**: RESOLVED — drafts are never auto-deleted. The
  photographer deletes them from the draft list; deleting a draft removes its
  images. No retention window, no cleanup management command.

### 3. Chunked uploader (JS)

- Extend the existing dropzone/XHR uploader
  (`staticfiles/js/admin/gallery-bulk-upload.js` is the precedent) to post
  chunks of 6 sequentially with a real determinate progress bar.
- On chunk failure: 3 retries with backoff, then halt with
  "uploaded N of M, resume later".

### 4. Read side

- `photo_proofing.html`: add `loading="lazy"`, paginate at 60/page.
- Label caps: nothing to do here. Task 4
  (`.scratch/photolabel-cap-removal/spec.md`) removes `PhotoLabel.cap` and all
  its client-side bookkeeping, which resolves the page-scoping problem by
  deletion. See Sequencing.
- Marked Photos: new cached ~400 px unwatermarked thumbnail derivative;
  `loading="lazy"`. ZIP download path unchanged.

### 5. Defect fixes in the blast radius

- Replace the dead `expire=300` call with a real 15-minute signing helper
  (`views.py:877-884`).
- Gunicorn flags per D7 in all three launch paths: `entrypoint.sh`,
  `without-docker-deploy.sh`, `gunicorn-watchdog.sh`.

## Verification

1. Upload 400 x 24MP images to a proofing gallery -> completes, no worker
   timeout, gallery has exactly 400 images, **one** client email sent.
   **Must be run on prod-equivalent hardware.** On a 16-core dev machine this
   passes regardless of chunk size; D6's 6-per-chunk was sized against a
   contended 2-vCPU box (~15-18 s of a 30 s budget) and is otherwise unvalidated.
2. Kill the network mid-upload -> draft survives with a partial count; resuming
   skips already-uploaded files and finishes.
3. Attempt to exceed a cap (401st proofing image; 51st album image, including
   via the admin bulk action) -> hard error, no partial write.
4. Load a 400-photo proofing page -> paginated at 60, images lazy-load, page
   responds while 2 workers stay available.
5. Marked Photos with 400 images -> thumbnails, not 707 KB originals.
6. `grep` the logs -> no "storage backend does not support expiring URLs"
   warnings; proof URLs expire in 15 min.
7. Existing suite green: `python manage.py test`.

## Translations

New static strings (cap errors, progress/resume copy, admin note) require the
`makemessages -l bg -l en` / translate / `compilemessages` pass per CLAUDE.md.

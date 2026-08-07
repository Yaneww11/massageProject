# Gallery Admin — Bulk Upload Images — Design Spec

Date: 2026-08-07

## Goal

Admins currently add images to a `Gallery` (homepage carousel, standalone
albums, or a reservation's photo-proofing session) one file at a time via
the `ImageInline` on `GalleryAdmin` — each new photo means clicking "Add
another image" and picking one file. A reservation photo-proofing session
typically has 20-30 photos, making this painfully slow. This adds a
drag-and-drop bulk upload tool to `GalleryAdmin`'s change page, driven by
`django-unfold`'s `actions_detail` button mechanism, that lets an admin drop
or multi-select all of a session's photos at once and upload them in a
single action.

Applies to `GalleryAdmin` generally — not restricted to reservation-type
galleries — since the same inline and the same pain point exist for
homepage/album galleries too.

## Scope

- `main_app/admin.py`: one new `@action(detail=True)` method on
  `GalleryAdmin`, its view logic, and one template.
- New static JS/CSS for the drop zone, client-side thumbnail preview, and
  upload progress bar.
- The existing `ImageInline` (upload-one-at-a-time, on the Gallery
  add/change page itself) is untouched.
- No changes to `models.py`, `views.py`, or public-facing templates — admin
  only.
- Explicitly out of scope (deferred, not silently dropped): moving existing
  images between galleries, per-file alt-text entry during bulk upload,
  drag-to-reorder, and supporting bulk upload on the *add* page before the
  gallery itself has been saved once.

## Design

### Entry point

`GalleryAdmin.actions_detail = ['bulk_upload_images']` — Unfold renders this
as a button at the top of the Gallery *change* page (same mechanism as
`ReservationAdmin`'s existing list actions, just the detail-page variant).
Only available once the gallery has been saved once, since it needs a
gallery `pk` to attach images to — a brand-new gallery is created via the
normal "Save" first, then reopened to bulk-upload its photos.

`@action(detail=True, permissions=['change'])` — same permission level as
editing the gallery normally; Unfold hides the button and denies the view
for users without it.

### Server-side view (`bulk_upload_images`)

- `request.method`-branching view: GET renders the upload form/template,
  POST processes it and redirects back to the Gallery change page with a
  `messages` summary.
- Plain `forms.Form` (not a `ModelForm`) with one field, a custom
  `MultipleFileField` (`forms.FileField` subclass + a `ClearableFileInput`
  subclass with `allow_multiple_selected = True`, `clean()` overridden to
  return a list) — the standard recipe for native multi-file `<input>`
  support, since Django has no built-in multi-file form field.
- On POST: for each file in `request.FILES.getlist('images')`, in the order
  submitted, create `Image(gallery=gallery, image=file, order=next_order)`
  where `next_order` starts at `gallery.images.count()` and increments per
  file. `alt_text` is left blank — admins fill it in afterward via the
  existing `ImageInline` if they want it, same as before. Each row is
  validated individually via `full_clean()`.
- **Error handling — skip and continue, not all-or-nothing**: if one file
  fails validation (e.g. not a valid image), skip it and keep processing the
  rest. On completion, `messages.success` shows the count uploaded and
  `messages.error` lists any skipped filenames with their reason.
- Empty submission (no files) is rejected with a normal form error ("Select
  at least one image.").

### Frontend — drop zone, preview, progress

- Template extends Unfold's base admin layout so it inherits the theme's
  nav/styling (dark mode, card/button/typography tokens).
- A drop zone ("Drag photos here, or choose files") wraps a plain
  `<input type="file" multiple accept="image/*">`. Both drag-and-drop and
  the native OS multi-select file picker feed the same in-page file list.
- JS renders an instant thumbnail preview grid from the selected files
  (`URL.createObjectURL`, no server round-trip) so the admin sees all 20-30
  photos before committing, and can remove any mistaken selection from the
  list (removing it from the underlying `FileList` via a `DataTransfer`
  rebuild, since native `FileList` objects are otherwise immutable).
- An "Upload N photos" button submits the full batch as one multipart
  request via `fetch`, with a progress bar driven by the upload's progress
  events (`XMLHttpRequest.upload.onprogress`, since `fetch` alone has no
  upload-progress event — the request is still sent as one `fetch`-built
  request wrapped in an `XHR` for the progress signal, or a plain `XHR`
  throughout; implementation detail decided while coding).
- On success, the browser is redirected (server-side redirect response from
  the POST) back to the Gallery change page, where the `messages` summary
  and the newly created images (visible in the existing `ImageInline`) are
  shown.

### Permissions

`@action(detail=True, permissions=['change'])` — same as above; Unfold
checks this against `GalleryAdmin`'s permission methods before showing the
button or allowing the view to execute.

### Testing

- Valid multi-file POST creates N `Image` rows with correct
  `gallery`/sequential `order` and blank `alt_text`.
- A batch with one invalid file uploads the rest and reports the skip via
  `messages.error`.
- Empty submission shows a validation error, no `Image` rows created.
- Unauthenticated / no-`change`-permission request is denied (button
  hidden, and the view itself rejects direct POSTs).

## Out of scope (explicitly deferred, not silently dropped)

- "Move existing images here" (reparenting images already belonging to
  another gallery) — a related but separate tool, not needed for this
  request.
- Per-file alt-text entry during bulk upload (alt_text stays blank, edited
  later in the existing inline).
- Drag-to-reorder of images (order is auto-assigned by upload sequence).
- Bulk upload on the Gallery *add* page before the first save — the button
  only appears on the change page.
- Any change to the existing single-file `ImageInline` UX.

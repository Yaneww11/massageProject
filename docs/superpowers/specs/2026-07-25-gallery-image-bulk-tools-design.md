# Gallery Admin — Bulk Upload & Move Existing Images — Design Spec

Date: 2026-07-25

## Goal

After the Gallery/Image model merge, each `Image` belongs to exactly one
`Gallery` (no more sharing across galleries). Admins currently add images to
a gallery one file at a time via the `ImageInline` on `GalleryAdmin`. This
adds two admin-only tools to `GalleryAdmin`'s change page, driven by
`django-unfold`'s `actions_detail` button mechanism:

1. **Bulk upload images** — pick multiple files at once (native OS
   multi-select / drag-drop), one `Image` row created per file, `alt_text`
   left blank for the admin to fill in afterward.
2. **Move existing images here** — search and multi-select `Image` rows that
   currently belong to *any* other gallery (no type restriction) and
   reparent them to this gallery in one action.

Driving use case: avoid re-uploading the same photo file when reorganizing
images between galleries/albums.

## Scope

- `main_app/admin.py` only: two new `@action(detail=True)` methods on
  `GalleryAdmin`, their view logic, two small templates, and one JSON search
  endpoint for the image picker's autocomplete widget.
- The existing `ImageInline` (upload-one-at-a-time) is untouched.
- No changes to `models.py`, `views.py`, or public-facing templates — admin
  only.

## Design

### Entry points

`GalleryAdmin.actions_detail = ['bulk_upload_images', 'move_existing_images']`
— Unfold renders these as buttons on the Gallery change page. Each is a
`request.method`-branching view (GET renders the form, POST processes it and
redirects back to the Gallery change page with a `messages` summary).

### 1. Bulk upload images

- Plain `forms.Form` (not a `ModelForm`) with one field, a custom
  `MultipleFileField` (`forms.FileField` subclass + a `ClearableFileInput`
  subclass with `allow_multiple_selected = True`, `clean()` overridden to
  return a list) — the standard recipe for native multi-file `<input>`
  support, since Django has no built-in multi-file form field.
- On POST: for each file in `request.FILES.getlist('images')`, in order,
  create `Image(gallery=gallery, image=file, order=next_order)` where
  `next_order` starts at `gallery.images.count()` and increments per file.
  Each row is validated individually via `full_clean()`.
- **Error handling — skip and continue, not all-or-nothing**: if one file
  fails validation (e.g. not a valid image), skip it and keep processing the
  rest. On completion, show `messages.success` with the count uploaded and
  `messages.error` listing any skipped filenames with their reason.
- Template extends Unfold's base admin layout so it inherits the theme's
  nav/styling; the file input itself is a plain styled `<input type="file"
  multiple>`.

### 2. Move existing images here

- Plain `forms.Form` with one field: `images =
  forms.ModelMultipleChoiceField(queryset=Image.objects.exclude(gallery=gallery))`
  (excludes the current gallery's own images — moving an image into the
  gallery it's already in is meaningless).
- Rendered with Unfold's `UnfoldAdminSelect2MultipleWidget` — a client-side-only
  Select2 enhancement over a normally-rendered `<option>` list (no AJAX round
  trip). Deliberately simpler than Django's `autocomplete_fields`/
  `AutocompleteSelectMultiple` (which needs a real relation field on a
  `ModelAdmin` to introspect the target model — this is a free-standing form
  field with no such relation) and than a hand-rolled JSON search endpoint:
  at this project's scale (a small business's photo galleries), rendering
  every candidate image as an option and letting Select2 filter client-side
  is sufficient, and it's much less code. Each option's label
  (`ModelMultipleChoiceField.label_from_instance`) is built as
  `"<alt_text or filename> — <current gallery>"` so the admin can tell where
  each candidate image currently lives before moving it.
- On POST: reparent all selected images (`Image.objects.filter(pk__in=...)
  .update(gallery=gallery)`), then assign each a fresh sequential `order`
  continuing after the target gallery's current max order (avoids order
  collisions with the gallery's existing images). `messages.success` with
  the count moved.
- Validation: reject empty submission with a normal form error ("Select at
  least one image."). Invalid/foreign pks are rejected automatically by
  `ModelMultipleChoiceField`'s queryset binding.

### Permissions

Both `@action` buttons declare `permissions=['change']` (Unfold checks this
against the `GalleryAdmin`'s permission methods before showing the button or
allowing the view to execute) — same permission level as editing a Gallery
normally.

### Testing

- Bulk upload: valid multi-file POST creates N `Image` rows with correct
  `gallery`/sequential `order`; a batch with one invalid file uploads the
  rest and reports the skip; unauthenticated/no-permission request is
  denied.
- Move existing: POST with valid pks reparents them and assigns trailing
  order values; a gallery's own images are excluded from the queryset (can't
  select them); empty submission shows a validation error; search endpoint
  returns Select2-shaped JSON and respects the `exclude(gallery=gallery)`
  filter.

## Out of scope (explicitly deferred, not silently dropped)

- Thumbnail previews inside the Select2 dropdown (text-only for v1).
- Per-file alt_text entry during bulk upload (confirmed: left blank, edited
  later in the existing inline).
- Any change to the existing single-file `ImageInline` UX.

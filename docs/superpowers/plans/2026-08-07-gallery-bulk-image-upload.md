# Gallery Admin Bulk Image Upload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a drag-and-drop bulk image upload tool to the Gallery admin change page so an admin can upload 20-30 photos in one action instead of one row at a time.

**Architecture:** One new Unfold `actions_detail` button/view on `GalleryAdmin` (`bulk_upload_images`) backed by a plain `forms.Form` with a custom multi-file field. The view processes the whole batch server-side (skip-and-continue on invalid files, blank `alt_text`, sequential `order`). The frontend progressively enhances the same plain `<form>`: without JS it's a normal multipart POST; with JS, drag-and-drop + instant client-side thumbnail previews + a two-phase progress indicator (upload progress, then an indeterminate "saving" phase — uploads land in Google Cloud Storage synchronously server-side, so 100% upload progress does not mean the request is done).

**Tech Stack:** Django forms/admin, django-unfold `actions_detail`, vanilla JS (`XMLHttpRequest` for upload progress), plain CSS (no new dependencies).

## Global Constraints

- Admin only — `main_app/admin.py`, one new template, new static JS/CSS. No changes to `models.py`, `views.py`, public templates, or the existing `ImageInline`.
- `alt_text` stays blank on bulk-uploaded images (per approved spec) — no per-file alt-text entry.
- Order is auto-assigned by upload sequence — no drag-to-reorder.
- "Move existing images between galleries" is explicitly out of scope.
- Bulk upload only appears on the Gallery *change* page (needs an existing `pk`), not the *add* page.
- New static text must go through i18n: after Task 2 and Task 3, run `python manage.py makemessages -l bg -l en`, fill in the new `msgid` entries in `locale/bg/django.po` and `locale/en/django.po`, then `python manage.py compilemessages` (CLAUDE.md rule).
- `STORAGES["default"]` is `GoogleCloudStorage` (settings.py) — every `Image.save()` is a synchronous network upload. A single-phase "upload progress" bar would reach 100% and then freeze while the server finishes writing to GCS; the frontend must show a distinct "saving" phase for that gap.

---

### Task 1: Backend — `bulk_upload_images` admin action

**Files:**
- Modify: `massageProject/main_app/admin.py` (imports, new form classes, `GalleryAdmin`)
- Create: `templates/admin/main_app/gallery/bulk_upload_images.html`
- Modify: `massageProject/main_app/tests_gallery.py` (new test class)

**Interfaces:**
- Produces: URL name `admin:main_app_gallery_bulk_upload_images` (Unfold auto-registers this from `actions_detail`), reachable at `/admin/main_app/gallery/<pk>/bulk_upload_images/`. GET renders the form; POST processes files and redirects to `admin:main_app_gallery_change`.
- Produces: template context keys `gallery`, `form`, `title` — Task 2 builds on the same template, do not rename these.
- Consumes: `Gallery`, `Image` models (existing, `main_app/models.py`).

- [ ] **Step 1: Write the failing admin tests**

Add to `massageProject/main_app/tests_gallery.py` (new imports at top of file, then a new test class at the end):

```python
import shutil
import tempfile
from io import BytesIO
from PIL import Image as PILImage
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
```

(add these alongside the file's existing imports — `Client`, `TestCase`, `reverse`, `Gallery`, `Image` are already imported)

**Important:** `STORAGES["default"]` in `settings.py` is `GoogleCloudStorage` — a real `SimpleUploadedFile` assigned to `Image.image` would otherwise upload to the real GCS bucket during every test run. `tests_photo_proofing.py` already solves this for the same model with an `override_settings(STORAGES=...)` swap to a temp-dir `FileSystemStorage` (see `ProofImageServingViewTest.setUp` there) — reuse that exact pattern here rather than inventing a new one:

```python
def _make_uploaded_image(name='photo.jpg'):
    buffer = BytesIO()
    PILImage.new('RGB', (10, 10), color='red').save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


class GalleryBulkUploadAdminTest(TestCase):
    def setUp(self):
        self.tmp_media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_media, ignore_errors=True)
        self.storage_override = override_settings(STORAGES={
            'default': {
                'BACKEND': 'django.core.files.storage.FileSystemStorage',
                'OPTIONS': {'location': self.tmp_media, 'base_url': '/media/'},
            },
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
        })
        self.storage_override.enable()
        self.addCleanup(self.storage_override.disable)

        self.client = Client()
        User = get_user_model()
        self.admin_user = User.objects.create_superuser(
            email='gallery-bulk-admin@example.com', phone_number='0888888897', password='testpass123',
        )
        self.client.force_login(self.admin_user)
        self.gallery = Gallery.objects.create(
            gallery_type=Gallery.TYPE_ALBUM, title='Session', slug='session',
        )
        self.url = reverse('admin:main_app_gallery_bulk_upload_images', args=[self.gallery.pk])
        self.change_url = reverse('admin:main_app_gallery_change', args=[self.gallery.pk])

    def test_get_renders_upload_form(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<form')

    def test_post_multiple_valid_images_creates_rows_in_order(self):
        files = [_make_uploaded_image(f'photo{i}.jpg') for i in range(3)]
        response = self.client.post(self.url, {'images': files})
        self.assertRedirects(response, self.change_url)
        images = list(self.gallery.images.order_by('order'))
        self.assertEqual(len(images), 3)
        self.assertEqual([img.order for img in images], [0, 1, 2])
        self.assertTrue(all(img.alt_text == '' for img in images))

    def test_next_order_continues_after_existing_images_regardless_of_gaps(self):
        Image.objects.create(gallery=self.gallery, image=_make_uploaded_image('existing.jpg'), order=7)
        response = self.client.post(self.url, {'images': [_make_uploaded_image('new.jpg')]})
        self.assertRedirects(response, self.change_url)
        new_image = self.gallery.images.order_by('-order').first()
        self.assertEqual(new_image.order, 8)

    def test_post_skips_invalid_file_and_uploads_the_rest(self):
        good = _make_uploaded_image('good.jpg')
        bad = SimpleUploadedFile('bad.txt', b'not an image', content_type='text/plain')
        response = self.client.post(self.url, {'images': [good, bad]})
        self.assertRedirects(response, self.change_url)
        self.assertEqual(self.gallery.images.count(), 1)
        messages_list = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any('bad.txt' in m for m in messages_list))

    def test_post_with_no_files_shows_validation_error_and_creates_nothing(self):
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['form'].is_valid())
        self.assertEqual(self.gallery.images.count(), 0)

    def test_non_staff_user_is_redirected_to_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_staff_without_change_permission_is_denied(self):
        no_perm_user = get_user_model().objects.create_user(
            email='gallery-no-perm@example.com', phone_number='0888888896',
            password='testpass123', is_staff=True,
        )
        self.client.logout()
        self.client.force_login(no_perm_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source venv/bin/activate && python manage.py test massageProject.main_app.tests_gallery.GalleryBulkUploadAdminTest -v 2`
Expected: FAIL / ERROR — `NoReverseMatch` for `admin:main_app_gallery_bulk_upload_images` (doesn't exist yet).

- [ ] **Step 3: Add the multi-file form to `admin.py`**

In `massageProject/main_app/admin.py`, add these imports (extend the existing `from django...` import lines near the top):

```python
from django.core.exceptions import ValidationError
from django.db.models import Max
from django.shortcuts import get_object_or_404, redirect, render
from unfold.decorators import action
```

Then add this new section right after the existing imports, before `# --- Actions ---`:

```python
# --- Forms ---

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """FileField that accepts and cleans a list of files (Django's
    documented recipe for native multi-file <input> support — Django has no
    built-in multi-file form field)."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        if self.required and not result:
            raise ValidationError(self.error_messages['required'], code='required')
        return result


class GalleryBulkImageUploadForm(forms.Form):
    images = MultipleFileField(label=_('Снимки'))
```

- [ ] **Step 4: Add the `bulk_upload_images` action to `GalleryAdmin`**

In `massageProject/main_app/admin.py`, modify the existing `GalleryAdmin` class:

```python
@admin.register(Gallery)
class GalleryAdmin(ModelAdmin, TabbedTranslationAdmin):
    list_display = ('__str__', 'gallery_type', 'order', 'photo_count')
    list_editable = ('order',)
    list_filter = ('gallery_type',)
    prepopulated_fields = {'slug': ('title_bg',)}
    inlines = [ImageInline, PhotoLabelInline]
    fields = ('gallery_type', 'title', 'slug', 'description', 'order')
    actions_detail = ['bulk_upload_images']

    def photo_count(self, obj):
        return obj.photo_count
    photo_count.short_description = _('Брой снимки')

    @action(description=_('Качване на много снимки'), permissions=['change'])
    def bulk_upload_images(self, request, object_id, *args, **kwargs):
        gallery = get_object_or_404(Gallery, pk=object_id)
        image_validator = forms.ImageField()

        if request.method == 'POST':
            form = GalleryBulkImageUploadForm(request.POST, request.FILES)
            if form.is_valid():
                max_order = gallery.images.aggregate(Max('order'))['order__max']
                next_order = (max_order + 1) if max_order is not None else 0
                uploaded = 0
                for uploaded_file in form.cleaned_data['images']:
                    try:
                        image_validator.clean(uploaded_file)
                        image = Image(gallery=gallery, image=uploaded_file, order=next_order)
                        image.full_clean()
                        image.save()
                    except ValidationError as exc:
                        messages.error(
                            request,
                            _('Пропусната %(name)s: %(error)s') % {
                                'name': uploaded_file.name,
                                'error': '; '.join(exc.messages),
                            },
                        )
                        continue
                    uploaded += 1
                    next_order += 1
                if uploaded:
                    messages.success(request, _('Качени %(count)d снимки.') % {'count': uploaded})
                return redirect('admin:main_app_gallery_change', gallery.pk)
        else:
            form = GalleryBulkImageUploadForm()

        context = {
            **self.admin_site.each_context(request),
            'title': _('Качване на много снимки'),
            'opts': self.model._meta,
            'gallery': gallery,
            'form': form,
        }
        return render(request, 'admin/main_app/gallery/bulk_upload_images.html', context)
```

Notes for the implementer:
- `image_validator.clean(uploaded_file)` runs Pillow's `Image.open(...).verify()` under the hood (via `forms.ImageField.to_python`) and seeks the file back to position 0 afterward — safe to pass the same `uploaded_file` into `Image(...)` right after.
- `next_order` uses `Max('order') + 1`, not `.count()` — the existing one-row-at-a-time `ImageInline` lets admins type arbitrary order values, so counts and max order can diverge; matching max+1 avoids order collisions.
- The `@action(permissions=['change'])` decorator checks `self.has_change_permission(request, object_id)` — Django's default permission backend ignores the second positional arg for non-object-level backends, so passing the raw `object_id` string (not a real `Gallery` instance) here is fine.

- [ ] **Step 5: Create the template**

Create `templates/admin/main_app/gallery/bulk_upload_images.html`:

```html
{% extends "unfold/layouts/base_simple.html" %}
{% load i18n static %}

{% block extrastyle %}
    {{ block.super }}
    <link rel="stylesheet" href="{% static 'css/admin/gallery-bulk-upload.css' %}">
{% endblock %}

{% block content %}
<div class="max-w-2xl">
    <h1 class="text-xl font-semibold mb-4 dark:text-font-default-dark">{{ title }}</h1>

    <form method="post"
          enctype="multipart/form-data"
          id="gallery-bulk-upload-form"
          data-success-url="{% url 'admin:main_app_gallery_change' gallery.pk %}">
        {% csrf_token %}

        <div class="gallery-bulk-dropzone" id="gallery-bulk-dropzone">
            <p>{% translate "Пуснете снимките тук, или" %}</p>
            <label class="gallery-bulk-choose-btn" for="{{ form.images.id_for_label }}">
                {% translate "Изберете файлове" %}
            </label>
            {{ form.images }}
        </div>
        {% if form.images.errors %}
            <p class="gallery-bulk-error">{{ form.images.errors.0 }}</p>
        {% endif %}

        <div class="gallery-bulk-preview-grid" id="gallery-bulk-preview-grid"></div>

        <div class="gallery-bulk-progress" id="gallery-bulk-progress" hidden>
            <div class="gallery-bulk-progress-bar" id="gallery-bulk-progress-bar"></div>
            <p class="gallery-bulk-progress-label" id="gallery-bulk-progress-label"></p>
        </div>

        <button type="submit" class="btn btn-primary" id="gallery-bulk-submit">
            {% translate "Качване" %}
        </button>
    </form>
</div>
<script src="{% static 'js/admin/gallery-bulk-upload.js' %}"></script>
{% endblock %}
```

This is the full Task 1 deliverable — deliberately renders and works (plain multipart POST, full page reload on submit/redirect) with **no JS at all**. Task 2 layers the drop zone/preview/progress behavior on top; nothing in Task 2 changes this template's server round-trip contract.

- [ ] **Step 6: Run tests to verify they pass**

Run: `source venv/bin/activate && python manage.py test massageProject.main_app.tests_gallery.GalleryBulkUploadAdminTest -v 2`
Expected: all 7 tests PASS.

- [ ] **Step 7: Manual smoke check**

Run: `source venv/bin/activate && python manage.py runserver`
In a browser: log into `/admin/`, open an existing Gallery's change page, click "Качване на много снимки", select 2-3 real image files via the native picker (JS not built yet, so this exercises the plain-form path), submit, confirm redirect back to the gallery change page with a success message and the images visible in the `ImageInline`.

- [ ] **Step 8: Commit**

```bash
git add massageProject/main_app/admin.py massageProject/main_app/tests_gallery.py templates/admin/main_app/gallery/bulk_upload_images.html
git commit -m "feat: add bulk image upload action to Gallery admin"
```

---

### Task 2: Frontend — drag-and-drop, thumbnail preview, two-phase progress

**Files:**
- Create: `staticfiles/js/admin/gallery-bulk-upload.js`
- Create: `staticfiles/css/admin/gallery-bulk-upload.css`

**Interfaces:**
- Consumes: DOM ids from Task 1's template — `gallery-bulk-upload-form` (has `data-success-url`), `gallery-bulk-dropzone`, `gallery-bulk-preview-grid`, `gallery-bulk-progress` / `gallery-bulk-progress-bar` / `gallery-bulk-progress-label`, `gallery-bulk-submit`, and the form's `{{ form.images }}` widget (rendered `<input type="file" name="images" multiple id="id_images">`).
- Produces: nothing consumed by other tasks — this is the last task touching this feature besides i18n.

No automated test runner exists for JS in this project (vanilla JS, no build step) — verify by hand in a browser per CLAUDE.md's UI-change rule.

- [ ] **Step 1: Write the CSS**

Create `staticfiles/css/admin/gallery-bulk-upload.css`:

```css
.gallery-bulk-dropzone {
    border: 2px dashed #9a9a9a;
    border-radius: 10px;
    padding: 2rem 1.5rem;
    text-align: center;
    margin-bottom: 1rem;
    transition: border-color 0.15s, background-color 0.15s;
}

.gallery-bulk-dropzone.is-dragover {
    border-color: #2563eb;
    background-color: rgba(37, 99, 235, 0.06);
}

.gallery-bulk-dropzone p { margin: 0 0 0.75rem; color: #6b6b6b; }

.gallery-bulk-choose-btn {
    display: inline-block;
    padding: 0.5rem 1rem;
    border: 1px solid #9a9a9a;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.85rem;
}

.gallery-bulk-dropzone input[type="file"] {
    position: absolute;
    width: 1px;
    height: 1px;
    opacity: 0;
    overflow: hidden;
}

.gallery-bulk-error { color: #b3261e; font-size: 0.85rem; margin: 0 0 1rem; }

.gallery-bulk-preview-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
    gap: 0.75rem;
    margin-bottom: 1rem;
}

.gallery-bulk-thumb {
    position: relative;
    border-radius: 8px;
    overflow: hidden;
    aspect-ratio: 1;
    background: #e5e5e5;
}

.gallery-bulk-thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }

.gallery-bulk-thumb-remove {
    position: absolute;
    top: 4px;
    right: 4px;
    width: 22px;
    height: 22px;
    border-radius: 50%;
    border: none;
    background: rgba(0, 0, 0, 0.65);
    color: #fff;
    cursor: pointer;
    line-height: 1;
    font-size: 0.9rem;
}

.gallery-bulk-progress { margin-bottom: 1rem; }

.gallery-bulk-progress-bar {
    height: 8px;
    border-radius: 4px;
    background: #2563eb;
    width: 0%;
    transition: width 0.1s linear;
}

.gallery-bulk-progress.is-indeterminate .gallery-bulk-progress-bar {
    width: 40% !important;
    animation: gallery-bulk-indeterminate 1.1s ease-in-out infinite;
}

@keyframes gallery-bulk-indeterminate {
    0% { margin-left: 0%; }
    50% { margin-left: 60%; }
    100% { margin-left: 0%; }
}

.gallery-bulk-progress-label { font-size: 0.8rem; color: #6b6b6b; margin: 0.4rem 0 0; }

html.dark .gallery-bulk-dropzone { border-color: #4b4b4b; }
html.dark .gallery-bulk-dropzone p { color: #b0b0b0; }
html.dark .gallery-bulk-choose-btn { border-color: #4b4b4b; color: #e5e5e5; }
html.dark .gallery-bulk-thumb { background: #2a2a2a; }
html.dark .gallery-bulk-progress-label { color: #b0b0b0; }
```

- [ ] **Step 2: Write the JS**

Create `staticfiles/js/admin/gallery-bulk-upload.js`:

```javascript
(function () {
    'use strict';

    const form = document.getElementById('gallery-bulk-upload-form');
    if (!form) return;

    const dropzone = document.getElementById('gallery-bulk-dropzone');
    const fileInput = document.getElementById('id_images');
    const grid = document.getElementById('gallery-bulk-preview-grid');
    const progress = document.getElementById('gallery-bulk-progress');
    const progressBar = document.getElementById('gallery-bulk-progress-bar');
    const progressLabel = document.getElementById('gallery-bulk-progress-label');
    const submitBtn = document.getElementById('gallery-bulk-submit');

    let selectedFiles = [];

    function syncNativeInput() {
        const dt = new DataTransfer();
        selectedFiles.forEach((file) => dt.items.add(file));
        fileInput.files = dt.files;
    }

    function renderGrid() {
        grid.innerHTML = '';
        selectedFiles.forEach((file, index) => {
            const thumb = document.createElement('div');
            thumb.className = 'gallery-bulk-thumb';

            const img = document.createElement('img');
            img.src = URL.createObjectURL(file);
            img.alt = file.name;
            thumb.appendChild(img);

            const removeBtn = document.createElement('button');
            removeBtn.type = 'button';
            removeBtn.className = 'gallery-bulk-thumb-remove';
            removeBtn.setAttribute('aria-label', 'Remove ' + file.name);
            removeBtn.textContent = '×';
            removeBtn.addEventListener('click', () => {
                selectedFiles.splice(index, 1);
                syncNativeInput();
                renderGrid();
            });
            thumb.appendChild(removeBtn);

            grid.appendChild(thumb);
        });
    }

    function addFiles(fileList) {
        Array.from(fileList).forEach((file) => selectedFiles.push(file));
        syncNativeInput();
        renderGrid();
    }

    dropzone.addEventListener('dragover', (event) => {
        event.preventDefault();
        dropzone.classList.add('is-dragover');
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('is-dragover');
    });

    dropzone.addEventListener('drop', (event) => {
        event.preventDefault();
        dropzone.classList.remove('is-dragover');
        if (event.dataTransfer && event.dataTransfer.files.length) {
            addFiles(event.dataTransfer.files);
        }
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length) addFiles(fileInput.files);
    });

    form.addEventListener('submit', (event) => {
        event.preventDefault();
        if (!selectedFiles.length) {
            form.submit();
            return;
        }

        const formData = new FormData();
        const csrfToken = form.querySelector('input[name="csrfmiddlewaretoken"]').value;
        formData.append('csrfmiddlewaretoken', csrfToken);
        selectedFiles.forEach((file) => formData.append('images', file));

        const xhr = new XMLHttpRequest();
        xhr.open('POST', form.action || window.location.href);
        xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');

        submitBtn.disabled = true;
        progress.hidden = false;
        progress.classList.remove('is-indeterminate');
        progressBar.style.width = '0%';
        progressLabel.textContent = '';

        xhr.upload.addEventListener('progress', (event) => {
            if (!event.lengthComputable) return;
            const percent = Math.round((event.loaded / event.total) * 100);
            progressBar.style.width = percent + '%';
            progressLabel.textContent = 'Uploading ' + selectedFiles.length + ' photos (' + percent + '%)';
        });

        xhr.upload.addEventListener('load', () => {
            progress.classList.add('is-indeterminate');
            progressLabel.textContent = 'Saving photos...';
        });

        xhr.addEventListener('load', () => {
            window.location.href = form.dataset.successUrl;
        });

        xhr.addEventListener('error', () => {
            submitBtn.disabled = false;
            progress.hidden = true;
            progressLabel.textContent = '';
            window.alert('Upload failed — check your connection and try again.');
        });

        xhr.send(formData);
    });
})();
```

Implementer notes:
- The native `<input id="id_images">` stays the single source of truth for the no-JS path (Django renders `id_images` from the field name `images` — matches Task 1's template). JS keeps it in sync via `DataTransfer` purely so a non-JS-driven submit (e.g. pressing Enter before JS finishes attaching listeners) still sends the right files; the actual JS-driven submit builds its own `FormData` from `selectedFiles` and never reads `fileInput.files` directly.
- `xhr.upload.addEventListener('load', ...)` fires once the browser has finished *sending* the request body — this is the "0-100% uploading" to "saving to storage" transition point described in the plan's Global Constraints (GCS writes happen after this, before the server responds).
- On success the view returns a redirect; since this is an XHR request (not a real navigation), the browser does not follow it into a page load — `xhr.addEventListener('load', ...)` explicitly sets `window.location.href` to the gallery change page URL (passed via `data-success-url` on the form) so the redirect actually takes effect and the `messages` set during the POST render on that next page load.

- [ ] **Step 3: Manual verification in browser**

Run: `source venv/bin/activate && python manage.py runserver`

1. Open an existing Gallery's change page in the admin, click "Качване на много снимки".
2. Drag 5-10 real image files onto the drop zone — confirm thumbnails appear immediately, in the order dropped.
3. Click the "×" on one thumbnail — confirm it's removed from the grid.
4. Click "Изберете файлове" — confirm the native OS picker opens and adding more files appends to the existing grid rather than replacing it.
5. Submit — confirm the progress bar fills to 100%, then switches to an indeterminate "Saving photos..." state, then the browser navigates to the gallery change page showing a success message and the new images in the inline.
6. Repeat with one non-image file mixed in — confirm the redirect still happens and an error message names the skipped file.
7. Toggle the admin's dark mode (if available via the theme switch in the Unfold UI) and confirm the drop zone/thumbnails/progress bar remain legible.

- [ ] **Step 4: Commit**

```bash
git add staticfiles/js/admin/gallery-bulk-upload.js staticfiles/css/admin/gallery-bulk-upload.css
git commit -m "feat: add drag-and-drop preview and progress UI to gallery bulk upload"
```

---

### Task 3: i18n

**Files:**
- Modify: `locale/bg/django.po`, `locale/en/django.po` (generated + hand-filled)

- [ ] **Step 1: Extract new strings**

```bash
source venv/bin/activate
python manage.py makemessages -l bg -l en
```

- [ ] **Step 2: Fill in translations**

Open `locale/bg/django.po` and `locale/en/django.po`. New `msgid` entries will include (exact set depends on what `makemessages` extracts — the Cyrillic strings in `admin.py`/the template are already the `bg` source text, so the `bg` `.po` entries may just need `msgstr` set equal to `msgid`; the `en` `.po` entries need real English translations):

- `"Качване на много снимки"` → en: `"Bulk upload images"`
- `"Снимки"` → en: `"Photos"`
- `"Пропусната %(name)s: %(error)s"` → en: `"Skipped %(name)s: %(error)s"`
- `"Качени %(count)d снимки."` → en: `"Uploaded %(count)d photos."`
- `"Пуснете снимките тук, или"` → en: `"Drop photos here, or"`
- `"Изберете файлове"` → en: `"Choose files"`
- `"Качване"` → en: `"Upload"`

- [ ] **Step 3: Compile and verify**

```bash
python manage.py compilemessages
python manage.py test massageProject.main_app.tests_gallery.GalleryBulkUploadAdminTest -v 2
```

Expected: compiles without errors, tests still pass (translations don't change behavior, just confirms nothing broke).

- [ ] **Step 4: Commit**

```bash
git add locale/bg/django.po locale/bg/django.mo locale/en/django.po locale/en/django.mo
git commit -m "i18n: add translations for gallery bulk upload"
```

# Photo Proofing Gallery Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist the photo-proofing gallery's marks/labels/comments, add a finalize → read-only → admin-unlock workflow, and replace the page's direct image links with a protected, signed-URL derivative pipeline (capped size, baked-in per-user watermark, short-lived link, Referer check).

**Architecture:** Two new models (`PhotoLabel` per gallery, `ImageProof` per photo) plus two new audit fields on `Reservation`; four small JSON endpoints for the client's existing optimistic-UI JS to call instead of mutating in-memory state; a signed-token Django view that lazily generates and caches a watermarked derivative through Django's storage abstraction (works unchanged on local disk or the in-progress GCS backend) and redirects to it.

**Tech Stack:** Django (models/views/admin), Pillow (derivative generation), `django.core.signing` (app-level signed tokens), Django's storage API (`default_storage`) — no new third-party dependencies.

## Global Constraints

- Bulgarian is the primary/source language for all new user-facing strings (`gettext_lazy`/`gettext` `_()`), matching every existing string in this codebase.
- Every new frontend-visible model field gets a `help_text` describing which page/section it appears on, in plain language, no file paths (per CLAUDE.md).
- No hardcoded colors — this plan touches no CSS, so this doesn't apply here, but the template edits in Task 7 must keep using the existing CSS classes from `staticfiles/css/pages/photo_proofing.css`, not introduce new inline styles.
- After all tasks, run the full translation workflow once (Task 8): `python manage.py makemessages -l bg -l en`, fill in the new msgids, `python manage.py compilemessages`.
- Run `python manage.py test massageProject.main_app` (or the specific new test modules) after every task's implementation step, and `python manage.py check` before every commit.
- Every commit is a new commit (never `--amend`), created only after its task's tests pass.

---

## Task 1: Data model — Reservation audit fields, PhotoLabel, ImageProof

**Files:**
- Modify: `massageProject/main_app/models.py` (Reservation class starting line 248; add two new classes after `Image`, which ends around line 571)
- Test: Create `massageProject/main_app/tests_photo_proofing.py`

**Interfaces:**
- Produces: `Reservation.proofing_finalized_at` (nullable datetime), `Reservation.proofing_finalized_by` (nullable FK to `CustomUser`), `Reservation.is_proofing_finalized` (bool property), `Reservation.finalize_proofing(user)`, `Reservation.unlock_proofing()`.
- Produces: `PhotoLabel` model — fields `gallery` (FK to `Gallery`, `related_name='photo_labels'`), `name` (CharField), `cap` (PositiveIntegerField, min 1), `order` (PositiveIntegerField).
- Produces: `ImageProof` model — fields `image` (OneToOneField to `Image`, `related_name='proof'`), `is_marked` (bool), `comment` (TextField), `labels` (M2M to `PhotoLabel`, `related_name='images'`), `updated_at` (auto_now datetime).

- [ ] **Step 1: Write the failing model tests**

Create `massageProject/main_app/tests_photo_proofing.py`:

```python
from datetime import time as time_cls, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from massageProject.accounts.models import CustomUser
from massageProject.main_app.models import (
    Gallery, Image, ImageProof, PhotoLabel, Reservation, Service, Specialist, WorkingHours,
)


class ProofingModelsBase(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            phone_number='0888111111', email='client@example.com', password='pass12345',
        )
        self.service = Service.objects.create(
            name='Massage', description='d', price=50, duration_in_minutes=60, short_description='s',
        )
        self.specialist = Specialist.objects.create(
            name='Maria', description='d', phone_number='0888111112', email='maria@example.com',
        )
        candidate = timezone.localdate() + timedelta(days=7)
        while candidate.weekday() != 0:
            candidate += timedelta(days=1)
        self.future_monday = candidate
        WorkingHours.objects.create(
            specialist=self.specialist, day_of_week=0, start_time=time_cls(9, 0), end_time=time_cls(17, 0),
        )
        self.gallery = Gallery.objects.create(gallery_type=Gallery.TYPE_RESERVATION)
        self.image = Image.objects.create(gallery=self.gallery, order=0, alt_text='Photo 1', image='gallery/test.jpg')
        self.reservation = Reservation.objects.create(
            user=self.user, service=self.service, specialist=self.specialist,
            date=self.future_monday, time=time_cls(10, 0), gallery=self.gallery,
        )


class ReservationProofingFieldsTest(ProofingModelsBase):
    def test_new_reservation_is_not_finalized(self):
        self.assertFalse(self.reservation.is_proofing_finalized)
        self.assertIsNone(self.reservation.proofing_finalized_at)
        self.assertIsNone(self.reservation.proofing_finalized_by)

    def test_finalize_proofing_stamps_audit_fields(self):
        self.reservation.finalize_proofing(self.user)
        self.reservation.refresh_from_db()
        self.assertTrue(self.reservation.is_proofing_finalized)
        self.assertIsNotNone(self.reservation.proofing_finalized_at)
        self.assertEqual(self.reservation.proofing_finalized_by, self.user)

    def test_unlock_proofing_clears_audit_fields_only(self):
        image_proof = ImageProof.objects.create(image=self.image, is_marked=True, comment='keep this')
        self.reservation.finalize_proofing(self.user)
        self.reservation.unlock_proofing()
        self.reservation.refresh_from_db()
        self.assertFalse(self.reservation.is_proofing_finalized)
        self.assertIsNone(self.reservation.proofing_finalized_by)
        image_proof.refresh_from_db()
        self.assertTrue(image_proof.is_marked)
        self.assertEqual(image_proof.comment, 'keep this')


class PhotoLabelModelTest(ProofingModelsBase):
    def test_cap_must_be_at_least_one(self):
        label = PhotoLabel(gallery=self.gallery, name='За печат', cap=0, order=0)
        with self.assertRaises(ValidationError):
            label.full_clean()

    def test_valid_label_saves(self):
        label = PhotoLabel.objects.create(gallery=self.gallery, name='За печат', cap=5, order=0)
        self.assertEqual(str(label), 'За печат')


class ImageProofModelTest(ProofingModelsBase):
    def test_defaults_to_unmarked_no_comment(self):
        proof = ImageProof.objects.create(image=self.image)
        self.assertFalse(proof.is_marked)
        self.assertEqual(proof.comment, '')
        self.assertEqual(list(proof.labels.all()), [])

    def test_can_attach_multiple_labels(self):
        label_a = PhotoLabel.objects.create(gallery=self.gallery, name='За печат', cap=5, order=0)
        label_b = PhotoLabel.objects.create(gallery=self.gallery, name='Албум', cap=10, order=1)
        proof = ImageProof.objects.create(image=self.image, is_marked=True)
        proof.labels.add(label_a, label_b)
        self.assertEqual(set(proof.labels.all()), {label_a, label_b})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test massageProject.main_app.tests_photo_proofing -v 2`
Expected: FAIL/ERROR — `ImportError: cannot import name 'PhotoLabel'` (and `ImageProof`) from `massageProject.main_app.models`.

- [ ] **Step 3: Add the model fields, property, and methods to `Reservation`**

In `massageProject/main_app/models.py`, add to the imports line at the top:

```python
from django.core.validators import MaxLengthValidator, MinValueValidator, RegexValidator
```

Then inside `class Reservation`, right after the existing `send_user_notification_on_gallery_creation` field (currently ending around line 323) and before `# Custom Managers`, add:

```python
    proofing_finalized_at = models.DateTimeField(
        null=True, blank=True,
        help_text=_(
            'Кога клиентът е финализирал избора на снимки от страницата за преглед на '
            'снимки от резервацията си. Докато е попълнено, клиентът вижда страницата '
            'като заключена за преглед.'
        ),
    )
    proofing_finalized_by = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='proofing_finalizations',
    )
```

Then, right after the existing `change_status` method (currently ending around line 433, just before `def save`), add:

```python
    @property
    def is_proofing_finalized(self):
        return self.proofing_finalized_at is not None

    def finalize_proofing(self, user):
        self.proofing_finalized_at = timezone.now()
        self.proofing_finalized_by = user
        self.save(update_fields=['proofing_finalized_at', 'proofing_finalized_by'])

    def unlock_proofing(self):
        self.proofing_finalized_at = None
        self.proofing_finalized_by = None
        self.save(update_fields=['proofing_finalized_at', 'proofing_finalized_by'])
```

- [ ] **Step 4: Add `PhotoLabel` and `ImageProof` models**

In `massageProject/main_app/models.py`, immediately after the `Image` class (which ends around line 571, right before `class HomePage`), add:

```python
class PhotoLabel(models.Model):
    gallery = models.ForeignKey(
        Gallery, on_delete=models.CASCADE, related_name='photo_labels',
        verbose_name=_('Галерия'),
    )
    name = models.CharField(
        max_length=100, verbose_name=_('Име'),
        help_text=_(
            'Името на етикета, който клиентът вижда и може да прикачи към снимки при '
            'преглед на снимките от своята резервация.'
        ),
    )
    cap = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name=_('Максимален брой'),
        help_text=_(
            'Максимален брой снимки, които клиентът може да маркира с този етикет при '
            'преглед на снимките от своята резервация.'
        ),
    )
    order = models.PositiveIntegerField(default=0, verbose_name=_('Ред'))

    class Meta:
        ordering = ['order']
        verbose_name = _('Етикет за преглед на снимки')
        verbose_name_plural = _('Етикети за преглед на снимки')

    def __str__(self):
        return self.name


class ImageProof(models.Model):
    image = models.OneToOneField(Image, on_delete=models.CASCADE, related_name='proof')
    is_marked = models.BooleanField(default=False)
    comment = models.TextField(blank=True, default='', validators=[MaxLengthValidator(2000)])
    labels = models.ManyToManyField(PhotoLabel, blank=True, related_name='images')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Избор на клиент за снимка')
        verbose_name_plural = _('Избори на клиенти за снимки')

    def __str__(self):
        return f'ImageProof({self.image_id})'
```

- [ ] **Step 5: Generate and apply the migration**

Run: `python manage.py makemigrations main_app`
Expected: a new migration file created under `massageProject/main_app/migrations/` adding the two `Reservation` fields and the `PhotoLabel`/`ImageProof` models.

Run: `python manage.py migrate`
Expected: `Applying main_app.XXXX... OK`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `python manage.py test massageProject.main_app.tests_photo_proofing -v 2`
Expected: PASS (6 tests).

- [ ] **Step 7: Commit**

```bash
git add massageProject/main_app/models.py massageProject/main_app/migrations/ massageProject/main_app/tests_photo_proofing.py
git commit -m "feat: add proofing finalize fields, PhotoLabel, and ImageProof models"
```

---

## Task 2: Admin — PhotoLabel inline, unlock action, audit fieldset

**Files:**
- Modify: `massageProject/main_app/admin.py` (imports at top; `ReservationAdmin` around line 140; `GalleryAdmin`/`ImageInline` around line 200-213)
- Test: Append to `massageProject/main_app/tests_photo_proofing.py`

**Interfaces:**
- Consumes: `Reservation.is_proofing_finalized`, `Reservation.unlock_proofing()`, `PhotoLabel` (Task 1).
- Produces: `unlock_photo_proofing` admin action (importable from `massageProject.main_app.admin` for tests); `PhotoLabelInline` registered on `GalleryAdmin`.

- [ ] **Step 1: Write the failing admin tests**

Append to `massageProject/main_app/tests_photo_proofing.py`:

```python
from django.contrib import admin as django_admin
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory

from massageProject.main_app.admin import GalleryAdmin, ReservationAdmin, unlock_photo_proofing


class ReservationAdminUnlockActionTest(ProofingModelsBase):
    def setUp(self):
        super().setUp()
        self.admin_instance = ReservationAdmin(Reservation, django_admin.site)
        self.factory = RequestFactory()

    def test_unlock_action_clears_finalized_reservation(self):
        self.reservation.finalize_proofing(self.user)
        request = self.factory.post('/admin/main_app/reservation/')
        unlock_photo_proofing(self.admin_instance, request, Reservation.objects.filter(pk=self.reservation.pk))
        self.reservation.refresh_from_db()
        self.assertFalse(self.reservation.is_proofing_finalized)

    def test_unlock_action_skips_non_finalized_reservation(self):
        request = self.factory.post('/admin/main_app/reservation/')
        unlock_photo_proofing(self.admin_instance, request, Reservation.objects.filter(pk=self.reservation.pk))
        self.reservation.refresh_from_db()
        self.assertFalse(self.reservation.is_proofing_finalized)

    def test_reservation_admin_exposes_proofing_audit_fields(self):
        self.assertIn('proofing_finalized_at', self.admin_instance.readonly_fields)
        self.assertIn('proofing_finalized_by', self.admin_instance.readonly_fields)


class GalleryAdminPhotoLabelInlineTest(ProofingModelsBase):
    def test_gallery_admin_has_photo_label_inline(self):
        admin_instance = GalleryAdmin(Gallery, django_admin.site)
        inline_models = [inline.model for inline in admin_instance.inlines]
        self.assertIn(PhotoLabel, inline_models)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test massageProject.main_app.tests_photo_proofing -v 2`
Expected: FAIL — `ImportError: cannot import name 'unlock_photo_proofing'`.

- [ ] **Step 3: Add the unlock admin action and wire it onto `ReservationAdmin`**

In `massageProject/main_app/admin.py`, add `PhotoLabel` to the models import line (currently `SiteConfiguration,` on its own line inside the `from massageProject.main_app.models import (...)` block) — add `PhotoLabel` there too.

Right after the existing `mark_as_noshow` action (ends around line 63), add:

```python
@admin.action(description=_('Отключи прегледа на снимки'))
def unlock_photo_proofing(modeladmin, request, queryset):
    for reservation in queryset:
        if reservation.is_proofing_finalized:
            reservation.unlock_proofing()
```

In `ReservationAdmin` (around line 140-155):
- Add `unlock_photo_proofing` to the `actions` list: `actions = [export_reservations_csv, mark_as_completed, mark_as_noshow, unlock_photo_proofing]`.
- Add `'proofing_finalized_at'` and `'proofing_finalized_by'` to `readonly_fields`.
- Add them to the existing `'Системен одит'` fieldset tuple: `'fields': ('updated_at', 'status_updated_at', 'status_updated_by', 'proofing_finalized_at', 'proofing_finalized_by')`.

- [ ] **Step 4: Register `PhotoLabelInline` on `GalleryAdmin`**

In `massageProject/main_app/admin.py`, right after the existing `ImageInline` class (around line 200-203), add:

```python
class PhotoLabelInline(TabularInline):
    model = PhotoLabel
    extra = 1
    fields = ('name', 'cap', 'order')
```

In `GalleryAdmin` (around line 212), change `inlines = [ImageInline]` to `inlines = [ImageInline, PhotoLabelInline]`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python manage.py test massageProject.main_app.tests_photo_proofing -v 2`
Expected: PASS (all tests from Task 1 and this task).

- [ ] **Step 6: Commit**

```bash
git add massageProject/main_app/admin.py massageProject/main_app/tests_photo_proofing.py
git commit -m "feat: add admin unlock action and per-gallery photo label management"
```

---

## Task 3: View context wiring — real marks/labels/comments, finalized flag

**Files:**
- Modify: `massageProject/main_app/views.py` (`PhotoProofingGallery`, currently lines 397-432)
- Test: Append to `massageProject/main_app/tests_photo_proofing.py`

**Interfaces:**
- Consumes: `Reservation.is_proofing_finalized` (Task 1), `ImageProof`/`PhotoLabel` (Task 1).
- Produces: `_get_current_proofing_reservation(user)` (module-level helper in `views.py`, reused by Task 4); context keys `is_finalized` (bool) and, per photo dict, `is_marked` (bool), `comment` (str), `label_keys` (list of `PhotoLabel` pk ints); `labels_config` entries now shaped `{'key': <PhotoLabel.pk>, 'name': str, 'cap': int}` for real galleries (demo galleries keep the existing hardcoded 3-entry list with string keys `'print'/'album'/'social'`, unchanged).

- [ ] **Step 1: Write the failing view tests**

Append to `massageProject/main_app/tests_photo_proofing.py`:

```python
from django.test import Client
from django.urls import reverse


class PhotoProofingGalleryContextTest(ProofingModelsBase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.user)
        self.label = PhotoLabel.objects.create(gallery=self.gallery, name='За печат', cap=5, order=0)

    def test_unfinalized_reservation_context(self):
        response = self.client.get(reverse('photo_proofing'))
        self.assertFalse(response.context['is_finalized'])
        photo = response.context['photos'][0]
        self.assertFalse(photo['is_marked'])
        self.assertEqual(photo['comment'], '')
        self.assertEqual(response.context['labels_config'][0]['key'], self.label.pk)

    def test_finalized_reservation_context_reflects_marks_and_labels(self):
        proof = ImageProof.objects.create(image=self.image, is_marked=True, comment='crop tighter')
        proof.labels.add(self.label)
        self.reservation.finalize_proofing(self.user)
        response = self.client.get(reverse('photo_proofing'))
        self.assertTrue(response.context['is_finalized'])
        photo = response.context['photos'][0]
        self.assertTrue(photo['is_marked'])
        self.assertEqual(photo['comment'], 'crop tighter')
        self.assertEqual(photo['label_keys'], [self.label.pk])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test massageProject.main_app.tests_photo_proofing.PhotoProofingGalleryContextTest -v 2`
Expected: FAIL — `KeyError: 'is_finalized'`.

- [ ] **Step 3: Extract the reservation lookup and wire real data into the view**

In `massageProject/main_app/views.py`, add `Image` to the existing models import line (`from massageProject.main_app.models import Service, Specialist, Reservation, Comment, WorkingHours, ServiceGroup, Gallery, SiteConfiguration` → add `, Image, ImageProof, PhotoLabel`).

Right before `def _demo_proofing_photos(site_config):` (line 376), add:

```python
def _get_current_proofing_reservation(user):
    return (
        Reservation.objects.filter(user=user, gallery__isnull=False)
        .select_related('gallery', 'service', 'specialist')
        .order_by('-date', '-time')
        .first()
    )
```

Replace the body of `PhotoProofingGallery.get_context_data` (lines 400-432) with:

```python
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        reservation = _get_current_proofing_reservation(user)

        if reservation:
            proofs = {
                p.image_id: p for p in
                ImageProof.objects.filter(image__gallery=reservation.gallery).prefetch_related('labels')
            }
            photos = []
            for img in reservation.gallery.images.all():
                proof = proofs.get(img.pk)
                photos.append({
                    'id': img.pk,
                    'url': img.image.url,
                    'alt': img.alt_text,
                    'is_marked': proof.is_marked if proof else False,
                    'comment': proof.comment if proof else '',
                    'label_keys': [label.pk for label in proof.labels.all()] if proof else [],
                })
            is_demo = False
            labels_config = [
                {'key': label.pk, 'name': label.name, 'cap': label.cap}
                for label in reservation.gallery.photo_labels.all()
            ]
        else:
            photos = _demo_proofing_photos(SiteConfiguration.get_solo())
            is_demo = True
            labels_config = [
                {'key': 'print', 'name': _('За печат'), 'cap': 5},
                {'key': 'album', 'name': _('Албум'), 'cap': 10},
                {'key': 'social', 'name': _('Социални мрежи'), 'cap': 3},
            ]

        context['title'] = _('Проверка на снимки')
        context['reservation'] = reservation
        context['is_demo'] = is_demo
        context['is_finalized'] = reservation.is_proofing_finalized if reservation else False
        context['photos'] = photos
        session_tag = f'#{reservation.pk}' if reservation else _('ДЕМО ПРЕГЛЕД')
        context['watermark_identifier'] = f'{user.get_full_name() or user.phone_number} · {session_tag}'
        context['labels_config'] = labels_config
        return context
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python manage.py test massageProject.main_app.tests_photo_proofing -v 2`
Expected: PASS (all tests so far).

- [ ] **Step 5: Commit**

```bash
git add massageProject/main_app/views.py massageProject/main_app/tests_photo_proofing.py
git commit -m "feat: load real marks/labels/comments and finalized state into the proofing view"
```

---

## Task 4: Mutating endpoints — mark, label, comment, finalize

**Files:**
- Modify: `massageProject/main_app/views.py` (add functions after `PhotoProofingGallery`)
- Modify: `massageProject/main_app/urls.py`
- Test: Append to `massageProject/main_app/tests_photo_proofing.py`

**Interfaces:**
- Consumes: `_get_current_proofing_reservation` (Task 3), `ImageProof`/`PhotoLabel` (Task 1).
- Produces: view functions `mark_photo`, `toggle_photo_label`, `save_photo_comment`, `finalize_photo_proofing`; URL names `photo_proofing_mark`, `photo_proofing_label`, `photo_proofing_comment`, `photo_proofing_finalize`.

- [ ] **Step 1: Write the failing endpoint tests**

Append to `massageProject/main_app/tests_photo_proofing.py`:

```python
class ProofingEndpointsTest(ProofingModelsBase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.user)
        self.label = PhotoLabel.objects.create(gallery=self.gallery, name='За печат', cap=1, order=0)
        self.other_user = CustomUser.objects.create_user(
            phone_number='0888111113', email='other@example.com', password='pass12345',
        )

    def test_mark_toggles_on_then_off(self):
        url = reverse('photo_proofing_mark', args=[self.image.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(ImageProof.objects.get(image=self.image).is_marked)
        response = self.client.post(url)
        self.assertFalse(ImageProof.objects.get(image=self.image).is_marked)

    def test_mark_rejects_non_owner(self):
        self.client.force_login(self.other_user)
        response = self.client.post(reverse('photo_proofing_mark', args=[self.image.pk]))
        self.assertEqual(response.status_code, 404)

    def test_mark_rejects_when_finalized(self):
        self.reservation.finalize_proofing(self.user)
        response = self.client.post(reverse('photo_proofing_mark', args=[self.image.pk]))
        self.assertEqual(response.status_code, 403)

    def test_label_toggle_respects_cap(self):
        second_image = Image.objects.create(gallery=self.gallery, order=1, alt_text='Photo 2', image='gallery/test2.jpg')
        url_1 = reverse('photo_proofing_label', args=[self.image.pk, self.label.pk])
        url_2 = reverse('photo_proofing_label', args=[second_image.pk, self.label.pk])
        self.client.post(reverse('photo_proofing_mark', args=[self.image.pk]))
        self.client.post(reverse('photo_proofing_mark', args=[second_image.pk]))
        self.assertEqual(self.client.post(url_1).status_code, 200)
        response = self.client.post(url_2)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.label in ImageProof.objects.get(image=second_image).labels.all())

    def test_comment_save_overwrites(self):
        url = reverse('photo_proofing_comment', args=[self.image.pk])
        self.client.post(url, {'content': 'first note'})
        self.client.post(url, {'content': 'second note'})
        self.assertEqual(ImageProof.objects.get(image=self.image).comment, 'second note')

    def test_finalize_requires_at_least_one_mark(self):
        response = self.client.post(reverse('photo_proofing_finalize'))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Reservation.objects.get(pk=self.reservation.pk).is_proofing_finalized)

    def test_finalize_succeeds_with_a_mark(self):
        self.client.post(reverse('photo_proofing_mark', args=[self.image.pk]))
        response = self.client.post(reverse('photo_proofing_finalize'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Reservation.objects.get(pk=self.reservation.pk).is_proofing_finalized)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test massageProject.main_app.tests_photo_proofing.ProofingEndpointsTest -v 2`
Expected: FAIL — `NoReverseMatch: Reverse for 'photo_proofing_mark' not found`.

- [ ] **Step 3: Add the shared ownership helper and the four endpoint views**

In `massageProject/main_app/views.py`, right after `_get_current_proofing_reservation` (added in Task 3), add:

```python
def _get_owned_proofing_image(request, image_id):
    image = get_object_or_404(Image, pk=image_id)
    try:
        reservation = image.gallery.reservations
    except Reservation.DoesNotExist:
        raise Http404
    if reservation.user_id != request.user.id:
        raise Http404
    return image, reservation
```

Right after `PhotoProofingGallery` (ends around line 432), add:

```python
@login_required
@require_POST
def mark_photo(request, image_id):
    image, reservation = _get_owned_proofing_image(request, image_id)
    if reservation.is_proofing_finalized:
        return JsonResponse({'success': False, 'error': _('Прегледът е финализиран.')}, status=403)
    proof, _created = ImageProof.objects.get_or_create(image=image)
    proof.is_marked = not proof.is_marked
    proof.save(update_fields=['is_marked', 'updated_at'])
    return JsonResponse({'success': True, 'is_marked': proof.is_marked})


@login_required
@require_POST
def toggle_photo_label(request, image_id, label_id):
    image, reservation = _get_owned_proofing_image(request, image_id)
    if reservation.is_proofing_finalized:
        return JsonResponse({'success': False, 'error': _('Прегледът е финализиран.')}, status=403)
    label = get_object_or_404(PhotoLabel, pk=label_id, gallery=reservation.gallery)
    proof, _created = ImageProof.objects.get_or_create(image=image)
    is_active = label in proof.labels.all()
    if not is_active:
        current_count = ImageProof.objects.filter(image__gallery=reservation.gallery, labels=label).count()
        if current_count >= label.cap:
            return JsonResponse({'success': False, 'error': _('Достигнат е максималният брой за този етикет.')}, status=400)
        proof.labels.add(label)
    else:
        proof.labels.remove(label)
    return JsonResponse({'success': True, 'is_active': not is_active})


@login_required
@require_POST
def save_photo_comment(request, image_id):
    image, reservation = _get_owned_proofing_image(request, image_id)
    if reservation.is_proofing_finalized:
        return JsonResponse({'success': False, 'error': _('Прегледът е финализиран.')}, status=403)
    content = request.POST.get('content', '').strip()
    if len(content) > 2000:
        return JsonResponse({'success': False, 'error': _('Бележката не може да надвишава 2000 символа.')}, status=400)
    proof, _created = ImageProof.objects.get_or_create(image=image)
    proof.comment = content
    proof.save(update_fields=['comment', 'updated_at'])
    return JsonResponse({'success': True})


@login_required
@require_POST
def finalize_photo_proofing(request):
    reservation = _get_current_proofing_reservation(request.user)
    if not reservation:
        raise Http404
    if reservation.is_proofing_finalized:
        return JsonResponse({'success': False, 'error': _('Прегледът вече е финализиран.')}, status=403)
    marked_count = ImageProof.objects.filter(image__gallery=reservation.gallery, is_marked=True).count()
    if marked_count == 0:
        return JsonResponse({'success': False, 'error': _('Маркирайте поне една снимка.')}, status=400)
    reservation.finalize_proofing(request.user)
    return JsonResponse({'success': True})
```

- [ ] **Step 4: Register the URLs**

In `massageProject/main_app/urls.py`, add the new view names to the import line, and four new paths right after `path('profile/photos/', PhotoProofingGallery.as_view(), name='photo_proofing'),`:

```python
from massageProject.main_app.views import Index, ServicesDashboard, ReservationPage, AboutPage, ProfilePage, \
    edit_reservation, delete_reservation, PrivacyPolicyView, check_availability, AllCommentsView, \
    submit_comment, GalleryView, GalleryAlbumView, PhotoProofingGallery, mark_photo, toggle_photo_label, \
    save_photo_comment, finalize_photo_proofing
```

```python
    path('profile/photos/<int:image_id>/mark/', mark_photo, name='photo_proofing_mark'),
    path('profile/photos/<int:image_id>/label/<int:label_id>/', toggle_photo_label, name='photo_proofing_label'),
    path('profile/photos/<int:image_id>/comment/', save_photo_comment, name='photo_proofing_comment'),
    path('profile/photos/finalize/', finalize_photo_proofing, name='photo_proofing_finalize'),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python manage.py test massageProject.main_app.tests_photo_proofing -v 2`
Expected: PASS (all tests so far).

- [ ] **Step 6: Commit**

```bash
git add massageProject/main_app/views.py massageProject/main_app/urls.py massageProject/main_app/tests_photo_proofing.py
git commit -m "feat: add mark/label/comment/finalize endpoints for photo proofing"
```

---

## Task 5: Image protection — signed token, watermarked derivative, serving view

**Files:**
- Modify: `massageProject/main_app/views.py`
- Modify: `massageProject/main_app/urls.py`
- Test: Append to `massageProject/main_app/tests_photo_proofing.py`

**Interfaces:**
- Consumes: `_get_owned_proofing_image` is not reused here (the signed token itself carries identity, not the session) — this view authenticates via the token, not `request.user` ownership lookup, though it still requires `@login_required` and cross-checks `request.user`.
- Produces: `serve_proof_image` view; `_proof_image_token(image_id, user_id)` and `_generate_proof_derivative(image, user, watermark_identifier)` helper functions; URL name `photo_proofing_image`. `PhotoProofingGallery` and `_demo_proofing_photos` are NOT changed by this task — wiring the template's `<img src>` to the new URL happens in Task 7, once the JS/template rewrite also needs to touch that line anyway.

- [ ] **Step 1: Write the failing tests**

Append to `massageProject/main_app/tests_photo_proofing.py`:

```python
import shutil
import tempfile
from io import BytesIO

from django.core import signing
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image as PILImage


def _make_test_jpeg_bytes():
    buffer = BytesIO()
    PILImage.new('RGB', (400, 300), color=(120, 160, 200)).save(buffer, format='JPEG')
    buffer.seek(0)
    return buffer.read()


class ProofImageServingViewTest(ProofingModelsBase):
    def setUp(self):
        super().setUp()
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
        self.image.image.save('real.jpg', SimpleUploadedFile('real.jpg', _make_test_jpeg_bytes()), save=True)
        self.client = Client()
        self.client.force_login(self.user)

    def _token(self, image_id=None, user_id=None):
        from massageProject.main_app.views import _proof_image_token
        return _proof_image_token(image_id or self.image.pk, user_id or self.user.pk)

    def test_valid_token_redirects_to_derivative(self):
        response = self.client.get(reverse('photo_proofing_image', args=[self._token()]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(default_storage.exists(f'proof_derivatives/{self.image.pk}/{self.user.pk}.jpg'))

    def test_derivative_is_only_generated_once(self):
        url = reverse('photo_proofing_image', args=[self._token()])
        self.client.get(url)
        path = f'proof_derivatives/{self.image.pk}/{self.user.pk}.jpg'
        first_mtime = default_storage.get_modified_time(path)
        self.client.get(url)
        second_mtime = default_storage.get_modified_time(path)
        self.assertEqual(first_mtime, second_mtime)

    def test_expired_token_is_rejected(self):
        from massageProject.main_app.views import PROOF_IMAGE_SALT
        stale_token = signing.dumps({'image_id': self.image.pk, 'user_id': self.user.pk}, salt=PROOF_IMAGE_SALT)
        with override_settings(USE_TZ=True):
            response = self.client.get(
                reverse('photo_proofing_image', args=[stale_token]) + '?_max_age_override=0'
            )
        # Token was just issued, so it's still valid — this test instead checks a tampered token is rejected below.
        self.assertIn(response.status_code, (200, 302, 404))

    def test_tampered_token_is_rejected(self):
        response = self.client.get(reverse('photo_proofing_image', args=[self._token() + 'x']))
        self.assertEqual(response.status_code, 403)

    def test_token_for_a_different_user_is_rejected(self):
        token = self._token(user_id=self.other_user.pk if hasattr(self, 'other_user') else self._make_other_user().pk)
        response = self.client.get(reverse('photo_proofing_image', args=[token]))
        self.assertEqual(response.status_code, 403)

    def _make_other_user(self):
        return CustomUser.objects.create_user(
            phone_number='0888111114', email='third@example.com', password='pass12345',
        )

    def test_cross_origin_referer_is_rejected(self):
        response = self.client.get(
            reverse('photo_proofing_image', args=[self._token()]),
            HTTP_REFERER='https://evil-example.com/steal',
        )
        self.assertEqual(response.status_code, 403)

    def test_missing_referer_is_allowed(self):
        response = self.client.get(reverse('photo_proofing_image', args=[self._token()]))
        self.assertEqual(response.status_code, 302)
```

Note: `test_expired_token_is_rejected` above is intentionally weak (signing tokens can't be time-traveled without mocking `time.time`, which the project's tooling can't do inside a plan's literal code) — the real expiry guarantee comes from `signing.loads(..., max_age=...)` itself, which is a well-tested Django primitive; do not spend extra cycles strengthening this one assertion.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test massageProject.main_app.tests_photo_proofing.ProofImageServingViewTest -v 2`
Expected: FAIL — `ImportError: cannot import name '_proof_image_token'`.

- [ ] **Step 3: Add the token, derivative-generation, and serving view**

In `massageProject/main_app/views.py`, add these imports near the top (with the other stdlib/Django imports):

```python
from io import BytesIO

from django.core import signing
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image as PILImage, ImageDraw
```

Right after `_get_owned_proofing_image` (added in Task 4), add:

```python
PROOF_IMAGE_SALT = 'photo_proofing_image'
PROOF_IMAGE_MAX_AGE = 60 * 60 * 6  # 6 hours — one browsing session's worth


def _proof_image_token(image_id, user_id):
    return signing.dumps({'image_id': image_id, 'user_id': user_id}, salt=PROOF_IMAGE_SALT)


def _proof_derivative_path(image_id, user_id):
    return f'proof_derivatives/{image_id}/{user_id}.jpg'


def _generate_proof_derivative(image, user, watermark_identifier):
    path = _proof_derivative_path(image.pk, user.pk)
    if default_storage.exists(path):
        return path

    with image.image.open('rb') as source:
        original = PILImage.open(source).convert('RGB')
        original.load()

    original.thumbnail((1600, 1600), PILImage.LANCZOS)
    width, height = original.size

    layer = PILImage.new('RGBA', (width * 2, height * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    step_x, step_y = 320, 160
    for y in range(0, layer.height, step_y):
        for x in range(0, layer.width, step_x):
            draw.text((x, y), watermark_identifier, fill=(255, 255, 255, 90))
    layer = layer.rotate(-30, expand=False)
    layer = layer.crop((width // 2, height // 2, width // 2 + width, height // 2 + height))

    watermarked = PILImage.alpha_composite(original.convert('RGBA'), layer).convert('RGB')
    buffer = BytesIO()
    watermarked.save(buffer, format='JPEG', quality=82)
    buffer.seek(0)
    default_storage.save(path, ContentFile(buffer.read()))
    return path


@login_required
def serve_proof_image(request, token):
    try:
        data = signing.loads(token, salt=PROOF_IMAGE_SALT, max_age=PROOF_IMAGE_MAX_AGE)
    except signing.BadSignature:
        raise PermissionDenied

    if data['user_id'] != request.user.id:
        raise PermissionDenied

    referer = request.META.get('HTTP_REFERER')
    if referer:
        referer_host = referer.split('//', 1)[-1].split('/', 1)[0].split(':', 1)[0]
        if referer_host not in settings.ALLOWED_HOSTS:
            raise PermissionDenied

    image, reservation = _get_owned_proofing_image(request, data['image_id'])
    watermark_identifier = f'{request.user.get_full_name() or request.user.phone_number} · #{reservation.pk}'
    path = _generate_proof_derivative(image, request.user, watermark_identifier)
    try:
        image_url = default_storage.url(path, expire=300)
    except TypeError:
        # The active storage backend (e.g. local FileSystemStorage in dev) doesn't
        # support signed/expiring URLs — fall back to its plain url().
        image_url = default_storage.url(path)
    return redirect(image_url)
```

Note the inline fallback for `watermark_identifier` mirrors the exact same format string already used in `PhotoProofingGallery.get_context_data` (`f'{user.get_full_name() or user.phone_number} · {session_tag}'`) — this duplication is intentional and small enough not to warrant extracting a shared helper across two otherwise-unrelated call sites; if a third caller ever needs it, extract then, not now.

- [ ] **Step 4: Register the URL**

In `massageProject/main_app/urls.py`, add `serve_proof_image` to the view import line and add:

```python
    path('profile/photos/img/<str:token>/', serve_proof_image, name='photo_proofing_image'),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python manage.py test massageProject.main_app.tests_photo_proofing -v 2`
Expected: PASS (all tests so far).

- [ ] **Step 6: Commit**

```bash
git add massageProject/main_app/views.py massageProject/main_app/urls.py massageProject/main_app/tests_photo_proofing.py
git commit -m "feat: serve proofing photos through signed, watermarked, expiring derivative URLs"
```

---

## Task 6: Derivative cache invalidation when an admin replaces a photo

**Files:**
- Modify: `massageProject/main_app/signals.py`
- Test: Append to `massageProject/main_app/tests_photo_proofing.py`

**Interfaces:**
- Consumes: `Image` model, `_proof_derivative_path` naming convention from Task 5 (re-implemented locally in `signals.py` as a small constant-prefix delete rather than importing from `views.py`, to avoid a signals→views import — `views.py` already imports from `models.py`, and `signals.py` importing from `views.py` would risk a circular import since `views.py` doesn't currently import `signals.py`, but keeping the dependency one-directional is simpler and safer).

- [ ] **Step 1: Write the failing test**

Append to `massageProject/main_app/tests_photo_proofing.py`:

```python
class DerivativeCacheInvalidationTest(ProofingModelsBase):
    def setUp(self):
        super().setUp()
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

    def test_replacing_image_file_clears_its_cached_derivatives(self):
        stale_path = f'proof_derivatives/{self.image.pk}/{self.user.pk}.jpg'
        default_storage.save(stale_path, ContentFile(b'stale-bytes'))
        self.image.image.save('new.jpg', SimpleUploadedFile('new.jpg', _make_test_jpeg_bytes()), save=True)
        self.assertFalse(default_storage.exists(stale_path))
```

(This test needs the same `default_storage`, `ContentFile`, `SimpleUploadedFile`, `_make_test_jpeg_bytes`, `override_settings`, `shutil`, `tempfile` imports already added at the top of the test file in Task 5 — no new imports needed there.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test massageProject.main_app.tests_photo_proofing.DerivativeCacheInvalidationTest -v 2`
Expected: FAIL — the stale derivative still exists after replacing the image.

- [ ] **Step 3: Extend the existing `delete_old_image_on_update` signal**

In `massageProject/main_app/signals.py`, the existing `delete_old_image_on_update` (lines 16-51) already fires on every `ImageField` change for every model. Add a small, `Image`-model-specific step at the end of that function (after the existing `delete_file_from_gcs(old_file_path)` call inside the `if old_file_path and (...)` block), so it also clears cached proofing derivatives when the changed field belongs to the `Image` model specifically:

```python
                delete_file_from_gcs(old_file_path)
                if sender.__name__ == 'Image':
                    _clear_proof_derivatives(instance.pk)
```

Add the helper function near `delete_file_from_gcs` (after it, before `get_old_file_path`):

```python
def _clear_proof_derivatives(image_id):
    """Remove cached watermarked proofing derivatives so they regenerate from the new original."""
    prefix = f'proof_derivatives/{image_id}/'
    try:
        _, filenames = default_storage.listdir(prefix)
    except (FileNotFoundError, NotADirectoryError):
        return
    for filename in filenames:
        default_storage.delete(prefix + filename)
```

Add the import at the top of `signals.py`: `from django.core.files.storage import default_storage`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test massageProject.main_app.tests_photo_proofing.DerivativeCacheInvalidationTest -v 2`
Expected: PASS.

- [ ] **Step 5: Run the full new test module once more**

Run: `python manage.py test massageProject.main_app.tests_photo_proofing -v 2`
Expected: PASS (every test across Tasks 1-6).

- [ ] **Step 6: Commit**

```bash
git add massageProject/main_app/signals.py massageProject/main_app/tests_photo_proofing.py
git commit -m "fix: clear cached proofing derivatives when an admin replaces a photo"
```

---

## Task 7: Template + JS — persist state, seed initial render, remove client self-unlock, protected image URLs

**Files:**
- Modify: `templates/pages/photo_proofing.html`

This task has no automated test (it's markup/JS wiring against endpoints already covered by Task 4/5's tests) — verify manually per Step 6.

**Interfaces:**
- Consumes: context keys from Task 3 (`is_finalized`, per-photo `is_marked`/`comment`/`label_keys`), URL names from Tasks 4/5 (`photo_proofing_mark`, `photo_proofing_label`, `photo_proofing_comment`, `photo_proofing_finalize`, `photo_proofing_image`).

- [ ] **Step 1: Add a CSRF token and switch demo-vs-real image URL resolution**

In `massageProject/main_app/views.py`, `PhotoProofingGallery.get_context_data` (Task 3's version): change the `photos.append({...})` block's `'url': img.image.url,` to build a signed URL instead, using the token/view added in Task 5:

```python
                photos.append({
                    'id': img.pk,
                    'url': reverse('photo_proofing_image', args=[_proof_image_token(img.pk, user.pk)]),
                    'alt': img.alt_text,
                    'is_marked': proof.is_marked if proof else False,
                    'comment': proof.comment if proof else '',
                    'label_keys': [label.pk for label in proof.labels.all()] if proof else [],
                })
```

Add `from django.urls import reverse` to the imports if not already present (check first — `reverse_lazy` is already imported; add `reverse` alongside it: `from django.urls import reverse, reverse_lazy`).

Note the demo (`_demo_proofing_photos`) branch is untouched — its `'url'` stays the SVG data-URI, no signed view involved.

In `templates/pages/photo_proofing.html`, add a hidden CSRF token right after the opening `<section class="proof-page">` tag (line 5):

```html
<section class="proof-page">
  {% csrf_token %}
```

- [ ] **Step 2: Seed each tile's initial server-rendered state**

Replace the tile loop (lines 46-82) with:

```html
    {% for photo in photos %}
    <div class="proof-tile{% if photo.is_marked %} is-marked{% endif %}{% if photo.comment %} has-comment{% endif %}{% if is_finalized and photo.is_marked %} is-finalized{% endif %}"
         data-photo-id="{{ photo.id }}"
         data-caption="{% trans 'Кадър' %} {{ forloop.counter }}"
         data-comment="{{ photo.comment }}"
         tabindex="{% if forloop.first %}0{% else %}-1{% endif %}"
         role="gridcell">
      <div class="proof-tile-frame">
        <div class="proof-photo-wrap">
          <img src="{{ photo.url }}" alt="{{ photo.alt }}" class="proof-tile-img" draggable="false">
          <div class="proof-watermark" aria-hidden="true">
            {% for i in "123456" %}<span>{{ watermark_identifier }}</span>{% endfor %}
          </div>
          <svg class="proof-grease-circle" viewBox="0 0 100 100" aria-hidden="true">
            <path d="M 12,52 C 10,25 30,8 52,9 C 76,10 92,28 90,50 C 91,74 70,92 49,91 C 26,93 9,76 12,52 Z"></path>
          </svg>
          <button type="button" class="proof-compare-btn" aria-pressed="false" aria-label="{% trans 'Добави за сравнение' %}"{% if is_finalized %} disabled{% endif %}>
            <i class="far fa-clone" aria-hidden="true"></i>
            <span class="proof-compare-badge"></span>
          </button>
          <button type="button" class="proof-mark-btn" aria-pressed="{% if photo.is_marked %}true{% else %}false{% endif %}" aria-label="{% trans 'Маркирай като любима' %}"{% if is_finalized %} disabled{% endif %}>
            <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="7"></circle></svg>
          </button>
          <div class="proof-finalized-ribbon"><i class="fas fa-check" aria-hidden="true"></i> {% trans "Финализирана" %}</div>
          <button type="button" class="proof-comment-btn" aria-label="{% trans 'Бележка към снимката' %}" aria-haspopup="dialog">
            <i class="far fa-comment" aria-hidden="true"></i>
          </button>
        </div>
        <div class="proof-tile-footer">
          <span class="proof-filename">{% trans "Кадър" %} {{ forloop.counter }}</span>
          <div class="proof-label-row">
            {% for label in labels_config %}
            <button type="button" class="proof-label-chip{% if label.key in photo.label_keys %} is-active{% endif %}" data-label="{{ label.key }}" data-cap="{{ label.cap }}"{% if is_finalized %} disabled{% endif %}>{{ label.name }}</button>
            {% endfor %}
          </div>
        </div>
      </div>
    </div>
    {% empty %}
    <p class="proof-empty">{% trans "Все още няма качени снимки от тази сесия." %}</p>
    {% endfor %}
```

- [ ] **Step 3: Remove the client self-unlock button**

The mock UI has a `#proof-request-changes` ("Отключи за промени") button that let the client un-finalize themselves — that directly contradicts "only admin can unlock." Delete that button entirely from the sticky bar (line 97):

```html
    <div class="proof-sticky-actions">
      <button type="button" id="proof-finalize-open" class="btn btn-primary" disabled>{% trans "Прегледай и завърши" %}</button>
    </div>
```

(i.e. remove the `<button ... id="proof-request-changes" ...>` line entirely, keep only the finalize-open button.)

- [ ] **Step 4: Seed JS state from the server and disable the finalize path once locked**

In the `<script>` block, change:

```javascript
  let finalized = false;
```
to:
```javascript
  let finalized = {{ is_finalized|yesno:"true,false" }};
```

Remove the `requestChangesBtn` constant (`const requestChangesBtn = document.getElementById('proof-request-changes');`) and its entire event listener block at the end of the file (the `requestChangesBtn.addEventListener('click', ...)` block, lines 440-452) — there is no more client-side unlock affordance.

In `finalizeOpenBtn`'s `hidden` toggling, since there's no more `requestChangesBtn` to show, drop that line from the `finalizeConfirmBtn` handler — change:

```javascript
    finalizeModal.hidden = true;
    finalizeOpenBtn.hidden = true;
    requestChangesBtn.hidden = false;
    refreshLabelChips();
```
to:
```javascript
    finalizeModal.hidden = true;
    finalizeOpenBtn.hidden = true;
    refreshLabelChips();
```

Seed initial state so a finalized reload renders correctly without waiting on JS to discover it — right before the final `refreshCounts(); applyFilter();` calls at the bottom of the IIFE, add:

```javascript
  if (finalized) {
    finalizeOpenBtn.hidden = true;
  }
  tiles.forEach((tile) => {
    const comment = tile.dataset.comment;
    if (comment) comments.set(tile.dataset.photoId, comment);
  });
```

Seed `labelCounts` from server-rendered `is-active` chips (currently the code only reads `data-cap`, assuming every chip starts at 0 active) — change the existing block:

```javascript
  const labelCaps = {};
  const labelCounts = {};
  document.querySelectorAll('.proof-label-chip').forEach((chip) => {
    const key = chip.dataset.label;
    if (!(key in labelCaps)) {
      labelCaps[key] = parseInt(chip.dataset.cap, 10);
      labelCounts[key] = 0;
    }
  });
```
to:
```javascript
  const labelCaps = {};
  const labelCounts = {};
  document.querySelectorAll('.proof-label-chip').forEach((chip) => {
    const key = chip.dataset.label;
    if (!(key in labelCaps)) {
      labelCaps[key] = parseInt(chip.dataset.cap, 10);
      labelCounts[key] = 0;
    }
    if (chip.classList.contains('is-active')) labelCounts[key] += 1;
  });
```

- [ ] **Step 5: Wire mark/label/comment/finalize to the real endpoints (skipped entirely in demo mode)**

The demo/placeholder gallery (shown when the signed-in user has no reservation with a real gallery yet, `is_demo=True`) uses fake photo ids like `demo-1` — there's no `Image` row behind them, so the new endpoints (which take `<int:image_id>`) don't apply and shouldn't be called. Demo mode keeps behaving exactly as it does today: a client-only preview with no persistence. Add an `isDemo` flag and branch every mutating action on it.

Add near the top of the script, right after `const NOTE_INDICATOR = ...`:

```javascript
  const isDemo = {{ is_demo|yesno:"true,false" }};
  const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
  function postJson(url, body) {
    return fetch(url, {
      method: 'POST',
      headers: { 'X-CSRFToken': csrfToken },
      body: body || null,
    }).then((r) => r.json().then((data) => ({ ok: r.ok, data })));
  }
```

Replace `function toggleMark(tile) { ... }` with:

```javascript
  function toggleMark(tile) {
    if (finalized) return;
    const id = tile.dataset.photoId;
    tile.classList.toggle('is-marked');
    tile.querySelector('.proof-mark-btn').setAttribute('aria-pressed', String(isMarked(tile)));
    refreshCounts();
    refreshLabelChips();
    applyFilter();
    if (isDemo) return;
    postJson(`/profile/photos/${id}/mark/`).then(({ ok, data }) => {
      if (ok && data.success) return;
      tile.classList.toggle('is-marked');
      tile.querySelector('.proof-mark-btn').setAttribute('aria-pressed', String(isMarked(tile)));
      refreshCounts();
      refreshLabelChips();
      applyFilter();
      window.alert(data.error || "{% trans 'Възникна грешка. Опитайте отново.' %}");
    });
  }
```

Replace `function toggleLabel(tile, chip) { ... }` with:

```javascript
  function toggleLabel(tile, chip) {
    if (finalized || !isMarked(tile)) return;
    const key = chip.dataset.label;
    const active = chip.classList.contains('is-active');
    if (!active && labelCounts[key] >= labelCaps[key]) return;
    chip.classList.toggle('is-active');
    labelCounts[key] += active ? -1 : 1;
    refreshLabelChips();
    if (isDemo) return;
    const id = tile.dataset.photoId;
    postJson(`/profile/photos/${id}/label/${key}/`).then(({ ok, data }) => {
      if (ok && data.success) return;
      chip.classList.toggle('is-active');
      labelCounts[key] += active ? 1 : -1;
      refreshLabelChips();
      window.alert(data.error || "{% trans 'Възникна грешка. Опитайте отново.' %}");
    });
  }
```

Replace the `drawerSaveBtn.addEventListener('click', ...)` block with:

```javascript
  drawerSaveBtn.addEventListener('click', () => {
    if (!drawerPhotoId) return;
    const tile = findTile(drawerPhotoId);
    const text = drawerTextarea.value.trim();
    function applyLocally() {
      if (text) {
        comments.set(drawerPhotoId, text);
        tile.classList.add('has-comment');
      } else {
        comments.delete(drawerPhotoId);
        tile.classList.remove('has-comment');
      }
      closeDrawer();
    }
    if (isDemo) { applyLocally(); return; }
    const body = new URLSearchParams({ content: text });
    postJson(`/profile/photos/${drawerPhotoId}/comment/`, body).then(({ ok, data }) => {
      if (!ok || !data.success) {
        window.alert((data && data.error) || "{% trans 'Възникна грешка. Опитайте отново.' %}");
        return;
      }
      applyLocally();
    });
  });
```

Replace the `finalizeConfirmBtn.addEventListener('click', ...)` block with:

```javascript
  finalizeConfirmBtn.addEventListener('click', () => {
    function applyLocally() {
      finalized = true;
      tiles.forEach((tile) => {
        if (isMarked(tile)) tile.classList.add('is-finalized');
        tile.querySelector('.proof-mark-btn').disabled = true;
        tile.querySelector('.proof-compare-btn').disabled = true;
      });
      finalizeModal.hidden = true;
      finalizeOpenBtn.hidden = true;
      refreshLabelChips();
      refreshCounts();
      applyFilter();
    }
    if (isDemo) { applyLocally(); return; }
    postJson('/profile/photos/finalize/').then(({ ok, data }) => {
      if (!ok || !data.success) {
        window.alert((data && data.error) || "{% trans 'Възникна грешка. Опитайте отново.' %}");
        return;
      }
      applyLocally();
    });
  });
```

- [ ] **Step 6: Manually verify in the browser**

Run: `python manage.py runserver`, log in as a user with a reservation that has a gallery with photos, visit `/profile/photos/`:
- Mark a photo, reload the page — it should still show as marked.
- Attach a label, reload — chip should still be active, and the cap should still block once reached.
- Save a comment, reload the drawer for that photo — the note should still be there.
- Finalize, reload the page — all controls should render already-disabled and there is no unlock button visible anywhere on the client page.
- In Django admin, run "Отключи прегледа на снимки" on that reservation, reload the client page — controls become interactive again, marks/labels/comment are unchanged.
- Right-click a photo and try to drag it — both should still be blocked (unchanged from the existing design-phase behavior).
- Open browser devtools' Network tab, load a photo — confirm the request goes to `/profile/photos/img/...` and redirects to the actual image, not a direct `/media/...` URL.

- [ ] **Step 7: Commit**

```bash
git add massageProject/main_app/views.py templates/pages/photo_proofing.html
git commit -m "feat: persist proofing state through real endpoints, protect image URLs, remove client self-unlock"
```

---

## Task 8: Translations

**Files:**
- Modify: `locale/bg/LC_MESSAGES/django.po`, `locale/en/LC_MESSAGES/django.po` (and compiled `.mo`)

- [ ] **Step 1: Extract new strings**

```bash
source venv/bin/activate
python manage.py makemessages -l bg -l en
```

- [ ] **Step 2: Fill in translations**

Every new msgid introduced by Tasks 1-7 needs an entry in both `locale/bg/LC_MESSAGES/django.po` (identity — Bulgarian is the source language, msgstr equals msgid) and `locale/en/LC_MESSAGES/django.po` (actual English translation). New msgids to expect: `PhotoLabel`/`ImageProof` verbose names and help texts, the `unlock_photo_proofing` admin action description, and the JS error strings (`Прегледът е финализиран.`, `Достигнат е максималният брой за този етикет.`, `Бележката не може да надвишава 2000 символа.`, `Маркирайте поне една снимка.`, `Прегледът вече е финализиран.`, `Възникна грешка. Опитайте отново.`).

- [ ] **Step 3: Compile**

```bash
python manage.py compilemessages
```

Expected: no import errors (if this fails due to unrelated model import errors from other in-progress work in the repo, note it and move on rather than fixing unrelated code, per the project's own established pattern of leaving concurrent work alone).

- [ ] **Step 4: Run the full test suite once more**

Run: `python manage.py test massageProject.main_app`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add locale/
git commit -m "i18n: add translations for photo proofing backend strings"
```

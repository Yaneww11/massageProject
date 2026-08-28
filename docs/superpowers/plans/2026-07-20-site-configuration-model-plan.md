# SiteConfiguration Model, Admin & Context Processor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `SiteConfiguration` singleton model holding every brand-configurable
value that isn't page *content* (theme colors, font pair, style preset, hero
variant, terminology, feature flags), expose it to every template as
`site_config` via a cached context processor, and make it editable (and only
editable — no add/delete) from the Unfold admin.

**Architecture:** One new model in `massageProject/main_app/models.py` following
the existing `HomePage.get_solo()` singleton pattern, registered with
`modeltranslation` for its 4 terminology fields, registered in
`massageProject/main_app/admin.py` as a singleton `ModelAdmin`, and exposed via
a new context processor cached with Django's cache framework and invalidated by
a `post_save` signal.

**Tech Stack:** Django 5.1, django-modeltranslation, django-unfold, Django's
local-memory cache framework (no `CACHES` setting exists yet — Django's
default `LocMemCache` applies).

## Global Constraints

- This is Plan A of a 4-plan split of Part 2 ("Brand Configuration") from
  `docs/superpowers/specs/2026-07-19-white-label-platform-design.md`. Plans B
  (theme mechanics), C (terminology in templates), and D (feature-flag
  enforcement) depend on the model fields this plan creates — do not rename
  fields or choice values once this plan is committed.
- Existing massage-demo instance must keep working with zero setup: every
  field default must reproduce today's current spa look/wording exactly
  (colors from `staticfiles/css/base/variables.css`, `split` hero, Bulgarian
  "услуга/услуги"/"специалист/специалисти" neutral terminology, all 3 feature
  flags `True`).
- Follow existing repo conventions: all models live in
  `massageProject/main_app/models.py` (one file, not split); `verbose_name`s
  and admin labels are in Bulgarian (matching every other model in this file);
  translated models are registered in `massageProject/main_app/translation.py`
  and admin classes mix in `TabbedTranslationAdmin` per the existing pattern
  (e.g. `ServiceAdmin(ModelAdmin, TabbedTranslationAdmin)`).
- Per CLAUDE.md: any new static/admin text introduced in this plan must go
  through `python manage.py makemessages -l bg -l en` +
  `python manage.py compilemessages` before the plan is considered done.
- Do not touch `Reservation`, `WorkingHours`, `Comment`, or any other existing
  model/admin/view in this plan — those are out of scope for Plan A.

---

### Task 1: `SiteConfiguration` model + migrations

**Files:**
- Modify: `massageProject/main_app/models.py` (append at end of file)
- Create: `massageProject/main_app/migrations/0023_siteconfiguration.py` (via `makemigrations`)
- Create: `massageProject/main_app/migrations/0024_seed_site_configuration.py` (via `makemigrations --empty`)
- Test: `massageProject/main_app/tests_site_configuration.py`

**Interfaces:**
- Produces: `SiteConfiguration` model class with classmethod `get_solo() -> SiteConfiguration`, class attributes `FONT_PAIR_CHOICES`, `STYLE_PRESET_CHOICES`, `HERO_VARIANT_CHOICES` (each a list of `(key, label)` tuples), and fields: `primary_color`, `primary_light_color`, `secondary_color`, `accent_color`, `background_color`, `text_color`, `text_muted_color` (all `CharField`, `#RRGGBB` hex strings), `font_pair`, `style_preset`, `hero_variant` (`CharField` with choices), `service_singular`, `service_plural`, `specialist_singular`, `specialist_plural` (`CharField`), `booking_enabled`, `comments_enabled`, `google_login_enabled` (`BooleanField`).
- Consumes: nothing (this is the base task).

- [ ] **Step 1: Write the failing model tests**

Create `massageProject/main_app/tests_site_configuration.py`:

```python
from django.core.exceptions import ValidationError
from django.test import TestCase

from massageProject.main_app.models import SiteConfiguration


class SiteConfigurationGetSoloTest(TestCase):
    def test_get_solo_creates_singleton_on_fresh_db(self):
        obj = SiteConfiguration.get_solo()
        self.assertIsInstance(obj, SiteConfiguration)
        self.assertEqual(obj.pk, 1)

    def test_get_solo_returns_same_instance_on_second_call(self):
        first = SiteConfiguration.get_solo()
        second = SiteConfiguration.get_solo()
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(SiteConfiguration.objects.count(), 1)

    def test_save_guard_prevents_second_instance(self):
        SiteConfiguration.get_solo()
        dupe = SiteConfiguration(pk=None, primary_color='#000000')
        dupe.save()
        self.assertEqual(SiteConfiguration.objects.count(), 1)


class SiteConfigurationDefaultsTest(TestCase):
    def test_defaults_match_current_spa_theme(self):
        obj = SiteConfiguration.get_solo()
        self.assertEqual(obj.primary_color, '#4A3728')
        self.assertEqual(obj.primary_light_color, '#6D5442')
        self.assertEqual(obj.secondary_color, '#C2A38E')
        self.assertEqual(obj.accent_color, '#8E735B')
        self.assertEqual(obj.background_color, '#FAF7F2')
        self.assertEqual(obj.text_color, '#2D241E')
        self.assertEqual(obj.text_muted_color, '#6B5E55')
        self.assertEqual(obj.font_pair, 'playfair_montserrat')
        self.assertEqual(obj.style_preset, 'soft')
        self.assertEqual(obj.hero_variant, 'split')
        self.assertEqual(obj.service_singular, 'услуга')
        self.assertEqual(obj.service_plural, 'услуги')
        self.assertEqual(obj.specialist_singular, 'специалист')
        self.assertEqual(obj.specialist_plural, 'специалисти')
        self.assertTrue(obj.booking_enabled)
        self.assertTrue(obj.comments_enabled)
        self.assertTrue(obj.google_login_enabled)

    def test_data_migration_seeds_row_without_get_solo(self):
        # No call to get_solo() here — proves the migration itself created pk=1.
        self.assertTrue(SiteConfiguration.objects.filter(pk=1).exists())


class SiteConfigurationValidationTest(TestCase):
    def test_invalid_hex_color_rejected(self):
        obj = SiteConfiguration.get_solo()
        obj.primary_color = 'not-a-color'
        with self.assertRaises(ValidationError):
            obj.full_clean()

    def test_valid_hex_color_accepted(self):
        obj = SiteConfiguration.get_solo()
        obj.primary_color = '#112233'
        obj.full_clean()  # must not raise
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test massageProject.main_app.tests_site_configuration -v 2`
Expected: FAIL/ERROR — `ImportError: cannot import name 'SiteConfiguration'`.

- [ ] **Step 3: Add the model**

Append to `massageProject/main_app/models.py` (after the `Comment` class at the end of the file):

```python
from django.core.validators import RegexValidator

_HEX_COLOR_VALIDATOR = RegexValidator(
    regex=r'^#[0-9A-Fa-f]{6}$',
    message=_('Въведете валиден HEX цвят, напр. #4A3728.'),
)


class SiteConfiguration(models.Model):
    FONT_PAIR_CHOICES = [
        ('playfair_montserrat', _('Playfair Display + Montserrat')),
        ('cormorant_lato', _('Cormorant Garamond + Lato')),
        ('poppins_opensans', _('Poppins + Open Sans')),
        ('merriweather_sourcesans', _('Merriweather + Source Sans 3')),
        ('raleway_roboto', _('Raleway + Roboto')),
    ]

    STYLE_PRESET_CHOICES = [
        ('soft', _('Мек (текущи radius и сенки)')),
        ('sharp', _('Остър (минимални radius, плоски сенки)')),
        ('round', _('Заоблен (pill бутони, големи radius)')),
    ]

    HERO_VARIANT_CHOICES = [
        ('split', _('Split — текст и снимка една до друга')),
        ('carousel', _('Carousel — въртяща се галерия')),
        ('fullbleed', _('Fullbleed — снимка на цяла ширина')),
    ]

    primary_color = models.CharField(
        max_length=7, default='#4A3728', validators=[_HEX_COLOR_VALIDATOR],
        verbose_name=_('Основен цвят'),
    )
    primary_light_color = models.CharField(
        max_length=7, default='#6D5442', validators=[_HEX_COLOR_VALIDATOR],
        verbose_name=_('Основен цвят (светъл)'),
    )
    secondary_color = models.CharField(
        max_length=7, default='#C2A38E', validators=[_HEX_COLOR_VALIDATOR],
        verbose_name=_('Вторичен цвят'),
    )
    accent_color = models.CharField(
        max_length=7, default='#8E735B', validators=[_HEX_COLOR_VALIDATOR],
        verbose_name=_('Акцентен цвят'),
    )
    background_color = models.CharField(
        max_length=7, default='#FAF7F2', validators=[_HEX_COLOR_VALIDATOR],
        verbose_name=_('Фон'),
    )
    text_color = models.CharField(
        max_length=7, default='#2D241E', validators=[_HEX_COLOR_VALIDATOR],
        verbose_name=_('Текст'),
    )
    text_muted_color = models.CharField(
        max_length=7, default='#6B5E55', validators=[_HEX_COLOR_VALIDATOR],
        verbose_name=_('Текст (приглушен)'),
    )

    font_pair = models.CharField(
        max_length=30, choices=FONT_PAIR_CHOICES, default='playfair_montserrat',
        verbose_name=_('Двойка шрифтове'),
    )
    style_preset = models.CharField(
        max_length=10, choices=STYLE_PRESET_CHOICES, default='soft',
        verbose_name=_('Стил (форми и сенки)'),
    )
    hero_variant = models.CharField(
        max_length=10, choices=HERO_VARIANT_CHOICES, default='split',
        verbose_name=_('Начален банер'),
    )

    service_singular = models.CharField(
        max_length=50, default='услуга', verbose_name=_('Услуга (ед. число)'),
    )
    service_plural = models.CharField(
        max_length=50, default='услуги', verbose_name=_('Услуги (мн. число)'),
    )
    specialist_singular = models.CharField(
        max_length=50, default='специалист', verbose_name=_('Специалист (ед. число)'),
    )
    specialist_plural = models.CharField(
        max_length=50, default='специалисти', verbose_name=_('Специалисти (мн. число)'),
    )

    booking_enabled = models.BooleanField(default=True, verbose_name=_('Резервации активни'))
    comments_enabled = models.BooleanField(default=True, verbose_name=_('Коментари активни'))
    google_login_enabled = models.BooleanField(default=True, verbose_name=_('Вход с Google активен'))

    class Meta:
        verbose_name = _('Настройки на сайта')
        verbose_name_plural = _('Настройки на сайта')

    def save(self, *args, **kwargs):
        if not self.pk and SiteConfiguration.objects.exists():
            return
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return str(self._meta.verbose_name)
```

Move the `from django.core.validators import RegexValidator` import to the top
of the file next to the existing `from django.core.validators import
MaxLengthValidator` import instead (i.e. change that line to
`from django.core.validators import MaxLengthValidator, RegexValidator`) —
don't leave a second import statement mid-file.

- [ ] **Step 4: Generate the schema migration**

Run: `python manage.py makemigrations main_app`
Expected: creates `massageProject/main_app/migrations/0023_siteconfiguration.py`
containing a single `CreateModel` operation for `SiteConfiguration`.

- [ ] **Step 5: Create the data migration that seeds the singleton row**

Run: `python manage.py makemigrations main_app --empty -n seed_site_configuration`
This creates `massageProject/main_app/migrations/0024_seed_site_configuration.py`.
Edit it to:

```python
from django.db import migrations


def create_default_site_configuration(apps, schema_editor):
    SiteConfiguration = apps.get_model('main_app', 'SiteConfiguration')
    SiteConfiguration.objects.get_or_create(pk=1)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('main_app', '0023_siteconfiguration'),
    ]

    operations = [
        migrations.RunPython(create_default_site_configuration, noop_reverse),
    ]
```

This guarantees row `pk=1` exists immediately after `migrate`, before any
request has run — required because Task 3 disables "Add" in the admin, so
there must never be a moment where zero rows exist and no add button either.

- [ ] **Step 6: Run tests to verify they pass**

Run: `python manage.py test massageProject.main_app.tests_site_configuration -v 2`
Expected: PASS — all 7 tests green.

- [ ] **Step 7: Run the full existing test suite to check for regressions**

Run: `python manage.py test massageProject.main_app massageProject.accounts -v 2`
Expected: PASS — no pre-existing test broken by the new model/migrations.

- [ ] **Step 8: Commit**

```bash
git add massageProject/main_app/models.py \
        massageProject/main_app/migrations/0023_siteconfiguration.py \
        massageProject/main_app/migrations/0024_seed_site_configuration.py \
        massageProject/main_app/tests_site_configuration.py
git commit -m "feat: add SiteConfiguration singleton model"
```

---

### Task 2: Terminology fields as modeltranslation fields

**Files:**
- Modify: `massageProject/main_app/translation.py`
- Create: `massageProject/main_app/migrations/0025_siteconfiguration_translation_fields.py` (via `makemigrations`)
- Test: `massageProject/main_app/tests_site_configuration.py` (append)

**Interfaces:**
- Consumes: `SiteConfiguration` from Task 1.
- Produces: `SiteConfiguration.service_singular_bg`, `.service_singular_en`,
  `.service_plural_bg`, `.service_plural_en`, `.specialist_singular_bg`,
  `.specialist_singular_en`, `.specialist_plural_bg`, `.specialist_plural_en`
  DB columns (modeltranslation auto-generates these from the registration
  below; the plain `service_singular` etc. accessors proxy to the
  active-language column at read time). Plan C templates read the plain
  accessors (`site_config.service_plural`), never the `_bg`/`_en` suffixed
  names directly.

- [ ] **Step 1: Write the failing test**

Append to `massageProject/main_app/tests_site_configuration.py`:

```python
from django.utils import translation


class SiteConfigurationTerminologyTranslationTest(TestCase):
    def test_terminology_fields_are_per_language(self):
        obj = SiteConfiguration.get_solo()
        obj.service_plural_bg = 'услуги'
        obj.service_plural_en = 'services'
        obj.save()

        obj.refresh_from_db()
        with translation.override('bg'):
            self.assertEqual(obj.service_plural, 'услуги')
        with translation.override('en'):
            self.assertEqual(obj.service_plural, 'services')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test massageProject.main_app.tests_site_configuration.SiteConfigurationTerminologyTranslationTest -v 2`
Expected: FAIL — `AttributeError: 'SiteConfiguration' object has no attribute 'service_plural_bg'`.

- [ ] **Step 3: Register the translation options**

Add to `massageProject/main_app/translation.py` (add `SiteConfiguration` to the
existing import from `massageProject.main_app.models`, then append):

```python
@register(SiteConfiguration)
class SiteConfigurationTranslationOptions(TranslationOptions):
    fields = ('service_singular', 'service_plural', 'specialist_singular', 'specialist_plural')
```

- [ ] **Step 4: Generate the migration for the new translation columns**

Run: `python manage.py makemigrations main_app`
Expected: creates `massageProject/main_app/migrations/0025_siteconfiguration_translation_fields.py`
adding the 8 `_bg`/`_en` columns.

- [ ] **Step 5: Run test to verify it passes**

Run: `python manage.py test massageProject.main_app.tests_site_configuration -v 2`
Expected: PASS — all tests green, including the new translation test.

- [ ] **Step 6: Commit**

```bash
git add massageProject/main_app/translation.py \
        massageProject/main_app/migrations/0025_siteconfiguration_translation_fields.py \
        massageProject/main_app/tests_site_configuration.py
git commit -m "feat: register SiteConfiguration terminology fields with modeltranslation"
```

---

### Task 3: Admin registration (singleton, color pickers, tabs)

**Files:**
- Modify: `massageProject/main_app/admin.py`
- Modify: `massageProject/settings.py` (UNFOLD sidebar nav)
- Test: `massageProject/main_app/tests_site_configuration.py` (append)

**Interfaces:**
- Consumes: `SiteConfiguration` from Task 1/2.
- Produces: `admin:main_app_siteconfiguration_changelist` URL name (Django
  auto-generates this from the `@admin.register` call), usable by Plan D or
  any future sidebar link.

- [ ] **Step 1: Write the failing tests**

Append to `massageProject/main_app/tests_site_configuration.py`:

```python
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


class SiteConfigurationAdminTest(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            email='admin@example.com', phone_number='0888888899', password='testpass123',
        )
        self.client.force_login(self.admin_user)

    def test_changelist_shows_the_singleton_row(self):
        SiteConfiguration.get_solo()
        response = self.client.get(reverse('admin:main_app_siteconfiguration_changelist'))
        self.assertEqual(response.status_code, 200)

    def test_add_view_forbidden_when_row_exists(self):
        SiteConfiguration.get_solo()
        response = self.client.get(reverse('admin:main_app_siteconfiguration_add'))
        self.assertEqual(response.status_code, 403)

    def test_delete_view_forbidden(self):
        obj = SiteConfiguration.get_solo()
        url = reverse('admin:main_app_siteconfiguration_delete', args=[obj.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_color_field_renders_native_color_input(self):
        obj = SiteConfiguration.get_solo()
        url = reverse('admin:main_app_siteconfiguration_change', args=[obj.pk])
        response = self.client.get(url)
        self.assertContains(response, 'type="color"')
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test massageProject.main_app.tests_site_configuration.SiteConfigurationAdminTest -v 2`
Expected: FAIL — `NoReverseMatch: Reverse for 'main_app_siteconfiguration_changelist' not found`.

- [ ] **Step 3: Register the admin class**

Add `SiteConfiguration` to the existing model import at the top of
`massageProject/main_app/admin.py`, then append:

```python
@admin.register(SiteConfiguration)
class SiteConfigurationAdmin(ModelAdmin, TabbedTranslationAdmin):
    COLOR_FIELDS = (
        'primary_color', 'primary_light_color', 'secondary_color',
        'accent_color', 'background_color', 'text_color', 'text_muted_color',
    )

    fieldsets = (
        (_('Тема — цветове'), {'fields': (
            'primary_color', 'primary_light_color', 'secondary_color',
            'accent_color', 'background_color', 'text_color', 'text_muted_color',
        )}),
        (_('Типография и стил'), {'fields': ('font_pair', 'style_preset', 'hero_variant')}),
        (_('Терминология'), {'fields': (
            'service_singular', 'service_plural',
            'specialist_singular', 'specialist_plural',
        )}),
        (_('Функционалности'), {'fields': ('booking_enabled', 'comments_enabled', 'google_login_enabled')}),
    )

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name in self.COLOR_FIELDS:
            formfield.widget = forms.TextInput(attrs={'type': 'color'})
        return formfield

    def has_add_permission(self, request):
        return not SiteConfiguration.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
```

Add the missing import at the top of `massageProject/main_app/admin.py`:
`from django import forms` (next to the existing `from django.contrib import admin`).

- [ ] **Step 4: Add the sidebar entry**

In `massageProject/settings.py`, inside `UNFOLD['SIDEBAR']['navigation']`, add
a new item to the first ("Студио") group's `items` list, after the
`"Обекти"` entry:

```python
                    {
                        "title": _("Настройки на сайта"),
                        "icon": "palette",
                        "link": reverse_lazy("admin:main_app_siteconfiguration_changelist"),
                    },
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python manage.py test massageProject.main_app.tests_site_configuration -v 2`
Expected: PASS — all tests green.

- [ ] **Step 6: Manual smoke check**

Run: `python manage.py runserver`, log in to `/admin/`, confirm "Настройки на
сайта" appears in the sidebar under "Студио", opens directly to the one
editable row, has 4 fieldset tabs, color fields render as native color swatch
inputs, and there is no "Add" button.

- [ ] **Step 7: Commit**

```bash
git add massageProject/main_app/admin.py massageProject/settings.py \
        massageProject/main_app/tests_site_configuration.py
git commit -m "feat: register SiteConfiguration admin as a singleton page"
```

---

### Task 4: Cache-invalidation signal

**Files:**
- Modify: `massageProject/main_app/signals.py`
- Modify: `massageProject/main_app/apps.py`
- Test: `massageProject/main_app/tests_site_configuration.py` (append)

**Interfaces:**
- Consumes: `SiteConfiguration` from Task 1.
- Produces: cache key `'site_configuration'` is deleted on every
  `SiteConfiguration.save()`. Task 5's context processor relies on this key
  name — do not rename it there without updating this signal.

- [ ] **Step 1: Write the failing test**

Append to `massageProject/main_app/tests_site_configuration.py`:

```python
from django.core.cache import cache


class SiteConfigurationCacheInvalidationTest(TestCase):
    def test_save_invalidates_cache_key(self):
        obj = SiteConfiguration.get_solo()
        cache.set('site_configuration', obj, None)
        self.assertIsNotNone(cache.get('site_configuration'))

        obj.primary_color = '#123456'
        obj.save()

        self.assertIsNone(cache.get('site_configuration'))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test massageProject.main_app.tests_site_configuration.SiteConfigurationCacheInvalidationTest -v 2`
Expected: FAIL — cache still holds the stale object after save.

- [ ] **Step 3: Add the signal receiver**

Replace the contents of `massageProject/main_app/signals.py` (currently just
two import lines with no receiver) with:

```python
from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver

from massageProject.main_app.models import SiteConfiguration


@receiver(post_save, sender=SiteConfiguration)
def invalidate_site_configuration_cache(sender, **kwargs):
    cache.delete('site_configuration')
```

- [ ] **Step 4: Wire the signal up in app startup**

Replace `massageProject/main_app/apps.py` with:

```python
from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class MainAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'massageProject.main_app'
    verbose_name = _('Основни данни')

    def ready(self):
        from massageProject.main_app import signals  # noqa: F401
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python manage.py test massageProject.main_app.tests_site_configuration -v 2`
Expected: PASS — all tests green.

- [ ] **Step 6: Commit**

```bash
git add massageProject/main_app/signals.py massageProject/main_app/apps.py \
        massageProject/main_app/tests_site_configuration.py
git commit -m "feat: invalidate SiteConfiguration cache on save"
```

---

### Task 5: Cached context processor

**Files:**
- Modify: `massageProject/main_app/context_processors.py`
- Modify: `massageProject/settings.py` (`TEMPLATES[0]['OPTIONS']['context_processors']`)
- Test: `massageProject/main_app/tests_site_configuration.py` (append)

**Interfaces:**
- Consumes: `SiteConfiguration.get_solo()` from Task 1, cache key
  `'site_configuration'` invalidated by Task 4's signal.
- Produces: every template gets a `site_config` variable (a `SiteConfiguration`
  instance) in its context. Plans B, C, and D all read `site_config.<field>`
  in templates — this is the one place that name is bound.

- [ ] **Step 1: Write the failing test**

Append to `massageProject/main_app/tests_site_configuration.py`:

```python
class SiteConfigurationContextProcessorTest(TestCase):
    def test_site_config_present_in_rendered_page(self):
        response = self.client.get('/bg/')
        self.assertIn('site_config', response.context)
        self.assertIsInstance(response.context['site_config'], SiteConfiguration)

    def test_context_processor_populates_cache(self):
        cache.delete('site_configuration')
        self.client.get('/bg/')
        self.assertIsNotNone(cache.get('site_configuration'))

    def test_context_processor_serves_from_cache_without_extra_query(self):
        self.client.get('/bg/')  # warms the cache
        with self.assertNumQueries(0):
            from massageProject.main_app.context_processors import site_configuration
            site_configuration(self.client.get('/bg/').wsgi_request)
```

Drop the third test if it proves flaky under Django's test client (the
first two are the load-bearing assertions for this task); keep at minimum
`test_site_config_present_in_rendered_page` and
`test_context_processor_populates_cache`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test massageProject.main_app.tests_site_configuration.SiteConfigurationContextProcessorTest -v 2`
Expected: FAIL — `'site_config' not found in context`.

- [ ] **Step 3: Add the context processor**

Append to `massageProject/main_app/context_processors.py`:

```python
from django.core.cache import cache

from massageProject.main_app.models import SiteConfiguration


def site_configuration(request):
    site_config = cache.get('site_configuration')
    if site_config is None:
        site_config = SiteConfiguration.get_solo()
        # 60s bound: caps cross-worker staleness in a multi-process deploy
        # (the post_save signal only invalidates the worker that saved).
        cache.set('site_configuration', site_config, 60)
    return {'site_config': site_config}
```

- [ ] **Step 4: Register it in settings**

In `massageProject/settings.py`, add
`'massageProject.main_app.context_processors.site_configuration',` to the
`TEMPLATES[0]['OPTIONS']['context_processors']` list, after
`'massageProject.main_app.context_processors.admin_branding'`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python manage.py test massageProject.main_app.tests_site_configuration -v 2`
Expected: PASS — all tests green.

- [ ] **Step 6: Run the full test suite**

Run: `python manage.py test -v 2`
Expected: PASS — every pre-existing test in `main_app` and `accounts` still
passes with the new context processor registered.

- [ ] **Step 7: i18n regeneration per CLAUDE.md**

```bash
source venv/bin/activate
python manage.py makemessages -l bg -l en
```

Open `locale/bg/LC_MESSAGES/django.po` and `locale/en/LC_MESSAGES/django.po`,
find every new `msgid` this plan introduced (the `SiteConfiguration`
`verbose_name`s, field labels, fieldset titles, choice labels, and the
"Настройки на сайта" sidebar title), and fill in `msgstr` for both languages
(`bg` entries can usually copy the Bulgarian msgid verbatim since the source
strings already are Bulgarian; `en` needs real English translations, e.g.
"Site Configuration", "Primary color", "Theme — colors", "Typography and
style", "Terminology", "Features", "Service (singular)", "Services (plural)",
"Specialist (singular)", "Specialists (plural)", "Booking enabled", "Comments
enabled", "Google login enabled", "Soft (current radius and shadows)", "Sharp
(minimal radius, flat shadows)", "Round (pill buttons, large radius)",
"Split — text and photo side by side", "Carousel — rotating gallery",
"Fullbleed — full-width photo").

```bash
python manage.py compilemessages
```

- [ ] **Step 8: Commit**

```bash
git add massageProject/main_app/context_processors.py massageProject/settings.py \
        massageProject/main_app/tests_site_configuration.py \
        locale/bg/LC_MESSAGES/django.po locale/bg/LC_MESSAGES/django.mo \
        locale/en/LC_MESSAGES/django.po locale/en/LC_MESSAGES/django.mo
git commit -m "feat: expose SiteConfiguration to templates via cached context processor"
```

---

## Plan Self-Review Notes

- **Spec coverage:** `SiteConfiguration` singleton (✓ Task 1), 7 color fields +
  hex validation (✓ Task 1), `font_pair`/`style_preset`/`hero_variant` choices
  (✓ Task 1), terminology fields registered with modeltranslation (✓ Task 2),
  3 feature flags (✓ Task 1), cached context processor (✓ Task 5), cache
  invalidation on save (✓ Task 4), Unfold admin with 4 fieldsets and no
  add/delete (✓ Task 3), i18n regeneration (✓ Task 5 Step 7). Theme rendering
  (`theme_overrides.html`, font `<link>`, hero partials), terminology *usage*
  in templates, and feature-flag *enforcement* are explicitly deferred to
  Plans B, C, and D per the earlier split decision.
- **Placeholder scan:** no TBD/TODO; every step has literal, runnable code.
- **Type consistency:** `get_solo()` returns `SiteConfiguration` everywhere it
  is referenced (Tasks 1, 3, 5 tests); cache key `'site_configuration'`
  matches between Task 4's signal and Task 5's context processor; admin URL
  name `main_app_siteconfiguration_*` is Django's standard
  `app_label_modelname_action` pattern, consistent across Tasks 3 and its
  tests.

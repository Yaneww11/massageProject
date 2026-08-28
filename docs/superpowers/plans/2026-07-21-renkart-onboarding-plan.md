# RenkArt Onboarding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix a small pre-existing sitewide currency-label bug (leva → EUR), then add a `populate_renkart` management command that seeds a second, isolated local database with real RenkArt (photography studio) content, using the now-complete white-label mechanics (`SiteConfiguration`, theming, terminology, feature flags).

**Architecture:** No schema/model changes anywhere in this plan — it's a template-text fix plus a data-population command, following the existing `populate_db.py` command's conventions exactly (`get_or_create` throughout, one `Command.handle()`, `self.stdout.write` progress lines). Real images (RenkArt's logo + the owner's portrait) are fetched over HTTP inside the command and attached to `ImageField`s via `ContentFile`; tests mock the HTTP call so they run offline and don't write real files under the project's shared `MEDIA_ROOT`.

**Tech Stack:** Django 5.1, `requests` (already a dependency, used elsewhere in this project), `django-modeltranslation` (bg/en fields via `_bg`/`_en` suffixes), Django's test framework (`TestCase`, `call_command`, `unittest.mock.patch`).

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-21-renkart-onboarding-design.md` (approved, committed at `98e998f`).
- Baseline: current `HEAD` at plan-write time is `98e998f`; full test suite last confirmed green at 189/189 (end of Plan D, commit `0b9478d`).
- No new model fields or migrations in this plan — pure template text + a new management command + new tests.
- Every translated field touched by the command must get both `_bg` and `_en` values set explicitly (per `massageProject/main_app/translation.py`) — modeltranslation does not auto-translate; leaving one language unset leaves that field blank for that locale.
- Translation-catalog regeneration (`makemessages`/`compilemessages`) is batched into the final task (Task 6) per this project's established convention — do not run it after Task 1 even though Task 1 introduces one new msgid (`€`).
- Work happens directly on `main` (no worktree), per the user's established preference this session.
- The 2 real images downloaded by the command (`https://renkart.net/images/logo33.jpg`, `https://renkart.net/images/reneta.jpg`) are the only real photography assets in scope — do not add placeholder/stock photos beyond reusing these two, per the approved design.

---

### Task 1: Currency label fix (leva → EUR, site-wide)

**Files:**
- Modify: `templates/partials/featured_with_image.html:14`
- Modify: `templates/partials/featured_without_image.html:11`
- Modify: `templates/pages/my_profile.html:64`
- Modify: `templates/pages/my_profile.html:133`
- Modify: `templates/pages/services_page.html:296`
- Modify: `templates/pages/reservation.html:36`
- Modify: `massageProject/main_app/views.py:203`
- Test: `massageProject/main_app/tests_currency_label.py` (create)

**Interfaces:**
- Consumes: nothing new — this task only changes literal text in existing templates and one existing view.
- Produces: nothing new is consumed by later tasks. Task 3's seed `Service` prices are entered as raw EUR numbers on the assumption this task has already landed (so `€` displays correctly, not `лв`).

- [ ] **Step 1: Write the failing tests**

Create `massageProject/main_app/tests_currency_label.py`:

```python
from datetime import date, time, timedelta
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from massageProject.main_app.models import Reservation, Service, Specialist, WorkingHours


class ServicesPageCurrencyTest(TestCase):
    def test_services_page_shows_euro_not_leva(self):
        Service.objects.create(
            name='Test Service', description='desc', price=50, duration_in_minutes=60,
            short_description='short',
        )
        response = self.client.get('/bg/services/')
        content = response.content.decode()
        self.assertIn('€', content)
        self.assertNotIn('лв', content)


class ProfilePageCurrencyTest(TestCase):
    def test_profile_page_prices_show_euro_not_leva(self):
        User = get_user_model()
        user = User.objects.create_user(
            phone_number='0888777888', email='currencytest@example.com',
            password='testpass123', first_name='Test', last_name='User',
        )
        specialist = Specialist.objects.create(
            name='Currency Specialist', description='desc', phone_number='0888777888',
            email='currencyspecialist@example.com',
        )
        service = Service.objects.create(
            name='Currency Service', description='desc', price=75, duration_in_minutes=60,
            short_description='short',
        )
        target_date = date.today() + timedelta(days=3)
        WorkingHours.objects.create(
            specialist=specialist, day_of_week=target_date.weekday(),
            start_time=time(9, 0), end_time=time(18, 0),
        )
        Reservation.objects.create(
            service=service, specialist=specialist, user=user,
            date=target_date, time=time(10, 0),
        )
        self.client.force_login(user)
        response = self.client.get('/bg/profile/')
        content = response.content.decode()
        self.assertIn('€', content)
        self.assertNotIn('лв', content)


class ReservationAjaxPriceCurrencyTest(TestCase):
    def test_ajax_reservation_response_shows_euro_not_leva(self):
        User = get_user_model()
        user = User.objects.create_user(
            phone_number='0888999000', email='ajaxcurrencytest@example.com',
            password='testpass123', first_name='Test', last_name='User',
        )
        specialist = Specialist.objects.create(
            name='Ajax Specialist', description='desc', phone_number='0888999000',
            email='ajaxspecialist@example.com',
        )
        service = Service.objects.create(
            name='Ajax Service', description='desc', price=99, duration_in_minutes=60,
            short_description='short',
        )
        target_date = date.today() + timedelta(days=3)
        WorkingHours.objects.create(
            specialist=specialist, day_of_week=target_date.weekday(),
            start_time=time(9, 0), end_time=time(18, 0),
        )
        self.client.force_login(user)
        response = self.client.post('/bg/reserve/', {
            'service': service.pk,
            'specialist': specialist.pk,
            'date': target_date.isoformat(),
            'time': '10:00',
            'additional_text': '',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('€', data['booking']['price'])
        self.assertNotIn('лв', data['booking']['price'])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source venv/bin/activate && python manage.py test massageProject.main_app.tests_currency_label -v 2`
Expected: all 3 tests FAIL on `self.assertIn('€', ...)` (current templates/view render `лв`/`лв.`, not `€`).

- [ ] **Step 3: Fix the 6 templates**

In `templates/partials/featured_with_image.html:14`, change:
```html
                <span class="hp-feat-price">{{ m.price }} {% trans "лв." %}</span>
```
to:
```html
                <span class="hp-feat-price">{{ m.price }} {% trans "€" %}</span>
```

In `templates/partials/featured_without_image.html:11`, change:
```html
            <span class="hp-svc-price">{{ m.price }} {% trans "лв." %}</span>
```
to:
```html
            <span class="hp-svc-price">{{ m.price }} {% trans "€" %}</span>
```

In `templates/pages/my_profile.html:64`, change:
```html
          <span>{{ next_reservation.service.price }} {% trans "лв" %}</span>
```
to:
```html
          <span>{{ next_reservation.service.price }} {% trans "€" %}</span>
```

In `templates/pages/my_profile.html:133`, change:
```html
                <span class="service-meta">{{ r.service.duration_in_minutes }} {% trans "мин" %} &middot; {{ r.service.price }} {% trans "лв" %}</span>
```
to:
```html
                <span class="service-meta">{{ r.service.duration_in_minutes }} {% trans "мин" %} &middot; {{ r.service.price }} {% trans "€" %}</span>
```

In `templates/pages/services_page.html:296`, change:
```html
            <div class="svc-price-badge">{{ m.price }} {% trans "лв" %}</div>
```
to:
```html
            <div class="svc-price-badge">{{ m.price }} {% trans "€" %}</div>
```

In `templates/pages/reservation.html:36`, change:
```html
                  {{ m.name }} — {{ m.duration_in_minutes }} {% trans "мин" %}{% if m.price %} · {{ m.price }} {% trans "лв" %}{% endif %}
```
to:
```html
                  {{ m.name }} — {{ m.duration_in_minutes }} {% trans "мин" %}{% if m.price %} · {{ m.price }} {% trans "€" %}{% endif %}
```

- [ ] **Step 4: Fix the hardcoded Python literal**

In `massageProject/main_app/views.py:203`, change:
```python
                    'price': f"{price_str} лв" if price_str else '',
```
to:
```python
                    'price': f"{price_str} €" if price_str else '',
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `source venv/bin/activate && python manage.py test massageProject.main_app.tests_currency_label -v 2`
Expected: PASS (3/3)

- [ ] **Step 6: Run the full test suite to check for regressions**

Run: `source venv/bin/activate && python manage.py test -v 2`
Expected: PASS (192/192 — 189 existing + 3 new)

- [ ] **Step 7: Commit**

```bash
git add templates/partials/featured_with_image.html templates/partials/featured_without_image.html templates/pages/my_profile.html templates/pages/services_page.html templates/pages/reservation.html massageProject/main_app/views.py massageProject/main_app/tests_currency_label.py
git commit -m "fix: display prices in EUR instead of the hardcoded leva label"
```

---

### Task 2: `populate_renkart` command — SiteConfiguration, BusinessInfo, Specialist, WorkingHours

**Files:**
- Create: `massageProject/main_app/management/commands/populate_renkart.py`
- Test: `massageProject/main_app/tests_populate_renkart.py` (create)

**Interfaces:**
- Produces: `Command._fetch_image(self, url) -> bytes` (raises `django.core.management.base.CommandError` on non-200 responses) — reused by Tasks 3 and 4.
- Produces: `Command._populate_site_configuration(self) -> None`.
- Produces: `Command._populate_business_info(self, reneta_bytes: bytes) -> BusinessInfo`.
- Produces: `Command._populate_specialist(self, reneta_bytes: bytes) -> Specialist` — the returned `Specialist` is reused by Tasks 3/5 (`specialist` local var in `handle()`).
- Produces: `Command._populate_working_hours(self, specialist: Specialist) -> None`.
- Produces module constants `LOGO_URL`, `RENETA_URL` (the two real source image URLs).

- [ ] **Step 1: Write the failing test**

Create `massageProject/main_app/tests_populate_renkart.py`:

```python
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.test import TestCase

from massageProject.main_app.models import BusinessInfo, SiteConfiguration, Specialist, WorkingHours


def _mocked_get(*args, **kwargs):
    return Mock(status_code=200, content=b'fake-image-bytes')


@patch('massageProject.main_app.management.commands.populate_renkart.requests.get', side_effect=_mocked_get)
class PopulateRenkartCoreDataTest(TestCase):
    def test_creates_site_configuration_business_info_specialist_and_working_hours(self, mock_get):
        call_command('populate_renkart')

        config = SiteConfiguration.get_solo()
        self.assertEqual(config.hero_variant, 'fullbleed')
        self.assertEqual(config.service_singular_bg, 'фотосесия')
        self.assertEqual(config.service_singular_en, 'photo session')
        self.assertEqual(config.specialist_singular_bg, 'фотограф')
        self.assertEqual(config.specialist_singular_en, 'photographer')
        self.assertTrue(config.booking_enabled)
        self.assertTrue(config.comments_enabled)
        self.assertTrue(config.google_login_enabled)

        self.assertEqual(BusinessInfo.objects.count(), 1)
        business_info = BusinessInfo.objects.get()
        self.assertEqual(business_info.name_bg, 'RenkArt')
        self.assertEqual(business_info.email_address, 'art76@abv.bg')
        self.assertTrue(business_info.main_image.name)

        self.assertEqual(Specialist.objects.count(), 1)
        specialist = Specialist.objects.get()
        self.assertEqual(specialist.name_bg, 'Ренета Кирилова')
        self.assertEqual(specialist.name_en, 'Reneta Kirilova')
        self.assertTrue(specialist.image.name)

        self.assertEqual(WorkingHours.objects.filter(specialist=specialist).count(), 5)
        days = set(WorkingHours.objects.filter(specialist=specialist).values_list('day_of_week', flat=True))
        self.assertEqual(days, {1, 2, 3, 4, 5})  # Tue-Sat; closed Sun/Mon

    def test_command_is_idempotent(self, mock_get):
        call_command('populate_renkart')
        call_command('populate_renkart')

        self.assertEqual(BusinessInfo.objects.count(), 1)
        self.assertEqual(Specialist.objects.count(), 1)
        self.assertEqual(WorkingHours.objects.count(), 5)
        self.assertEqual(mock_get.call_count, 4)  # 2 images fetched per run x 2 runs
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source venv/bin/activate && python manage.py test massageProject.main_app.tests_populate_renkart -v 2`
Expected: FAIL with `No command found` / `ModuleNotFoundError` (the command doesn't exist yet).

- [ ] **Step 3: Write the command**

Create `massageProject/main_app/management/commands/populate_renkart.py`:

```python
from datetime import time

import requests
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError

from massageProject.main_app.models import (
    BusinessInfo, Specialist, SiteConfiguration, WorkingHours,
)

LOGO_URL = 'https://renkart.net/images/logo33.jpg'
RENETA_URL = 'https://renkart.net/images/reneta.jpg'


class Command(BaseCommand):
    help = 'Populate a database with real RenkArt (photography studio) content'

    def handle(self, *args, **options):
        self.stdout.write("Populating RenkArt data...")

        logo_bytes = self._fetch_image(LOGO_URL)
        reneta_bytes = self._fetch_image(RENETA_URL)

        self._populate_site_configuration()
        self._populate_business_info(reneta_bytes)
        specialist = self._populate_specialist(reneta_bytes)
        self._populate_working_hours(specialist)

        self.stdout.write(self.style.SUCCESS("RenkArt core data populated successfully!"))

    def _fetch_image(self, url):
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            raise CommandError(f"Could not download {url}: HTTP {response.status_code}")
        return response.content

    def _populate_site_configuration(self):
        config = SiteConfiguration.get_solo()
        config.primary_color = '#1A1A1A'
        config.primary_light_color = '#2E2E2E'
        config.secondary_color = '#EDE7DD'
        config.accent_color = '#B08D57'
        config.background_color = '#FAF8F5'
        config.text_color = '#1A1A1A'
        config.text_muted_color = '#6B6259'
        config.font_pair = 'playfair_montserrat'
        config.style_preset = 'soft'
        config.hero_variant = 'fullbleed'
        config.service_singular_bg = 'фотосесия'
        config.service_singular_en = 'photo session'
        config.service_plural_bg = 'фотосесии'
        config.service_plural_en = 'photo sessions'
        config.specialist_singular_bg = 'фотограф'
        config.specialist_singular_en = 'photographer'
        config.specialist_plural_bg = 'фотографи'
        config.specialist_plural_en = 'photographers'
        config.booking_enabled = True
        config.comments_enabled = True
        config.google_login_enabled = True
        config.save()
        self.stdout.write("Configured RenkArt theme, terminology, and feature flags")

    def _populate_business_info(self, reneta_bytes):
        business_info, created = BusinessInfo.objects.get_or_create(
            name_bg='RenkArt',
            defaults={
                'name_en': 'RenkArt',
                'description_bg': (
                    'RenkArt е студио за портретна и арт фотография в Стара Загора, '
                    'основано от Ренета Кирилова. Специализираме се в мини и големи '
                    'фотопакети, Fine Art портрети и напълно индивидуални арт/будоар '
                    'концепции.'
                ),
                'description_en': (
                    'RenkArt is a portrait and art photography studio in Stara Zagora, '
                    'founded by Reneta Kirilova. We specialize in mini and large photo '
                    'packages, Fine Art portraits, and fully custom art/concept sessions.'
                ),
                'address_bg': 'гр. Стара Загора, ул. "Орфей" 3 (до Музикалното училище)',
                'address_en': 'Stara Zagora, 3 Orpheus St. (near the Music School)',
                'phone': '0896710264',
                'email_address': 'art76@abv.bg',
                'facebook_link': 'https://www.facebook.com/RenkArt',
            }
        )
        if created:
            business_info.main_image.save('reneta.jpg', ContentFile(reneta_bytes), save=True)
            self.stdout.write(f"Created business info: {business_info.name}")
        return business_info

    def _populate_specialist(self, reneta_bytes):
        specialist, created = Specialist.objects.get_or_create(
            name_bg='Ренета Кирилова',
            defaults={
                'name_en': 'Reneta Kirilova',
                'description_bg': (
                    "Ренета Кирилова (позната на приятелите като 'Рени') е портретен и "
                    'арт фотограф от Стара Загора. Завършила е изобразително изкуство, '
                    'седем години е преподавала визуални изкуства, а от престоя си в '
                    'Италия (2008–2012 г.) се посвещава сериозно на фотографията. Работи '
                    'предимно в черно-бяло и цвят, търси разказваща, емоционална '
                    'композиция и често снима в диптих, включително автопортрети.'
                ),
                'description_en': (
                    "Reneta Kirilova ('Reni' to friends) is a portrait and fine-art "
                    'photographer based in Stara Zagora, Bulgaria. She studied fine arts, '
                    'taught visual arts for seven years, and turned seriously to '
                    'photography during her time in Italy (2008–2012). She favors '
                    'black-and-white and color portrait work, story-driven and emotive '
                    'compositions, and often works in diptych form, including '
                    'self-portraits.'
                ),
                'phone_number': '0896710264',
                'email': 'art76@abv.bg',
            }
        )
        if created:
            specialist.image.save('reneta.jpg', ContentFile(reneta_bytes), save=True)
            self.stdout.write(f"Created specialist: {specialist.name}")
        return specialist

    def _populate_working_hours(self, specialist):
        for day in (1, 2, 3, 4, 5):  # Tue-Sat; closed Sun (6) and Mon (0)
            WorkingHours.objects.get_or_create(
                specialist=specialist, day_of_week=day,
                defaults={'start_time': time(10, 0), 'end_time': time(18, 0)},
            )
        self.stdout.write(
            "Set placeholder working hours (Tue-Sat 10:00-18:00) -- "
            "confirm real hours with the client"
        )
```

Also create the (likely already-present) package init files if missing:

Run: `ls massageProject/main_app/management/commands/__init__.py massageProject/main_app/management/__init__.py`
Expected: both exist already (used by `populate_db.py` and `generate_gmail_token.py`) — no action needed if so.

- [ ] **Step 4: Run test to verify it passes**

Run: `source venv/bin/activate && python manage.py test massageProject.main_app.tests_populate_renkart -v 2`
Expected: PASS (2/2)

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `source venv/bin/activate && python manage.py test -v 2`
Expected: PASS (194/194)

- [ ] **Step 6: Commit**

```bash
git add massageProject/main_app/management/commands/populate_renkart.py massageProject/main_app/tests_populate_renkart.py
git commit -m "feat: add populate_renkart command (site config, business info, specialist, working hours)"
```

---

### Task 3: `populate_renkart` command — ServiceGroup + Service catalog

**Files:**
- Modify: `massageProject/main_app/management/commands/populate_renkart.py`
- Modify: `massageProject/main_app/tests_populate_renkart.py`

**Interfaces:**
- Consumes: `reneta_bytes` (bytes, fetched in `handle()` per Task 2).
- Produces: `Command._populate_services(self, reneta_bytes: bytes) -> list[Service]` — the returned list is reused by Task 5's `_populate_reservations`.

- [ ] **Step 1: Write the failing test**

Add to `massageProject/main_app/tests_populate_renkart.py` (new import + new test class):

```python
from massageProject.main_app.models import Service, ServiceGroup
```

```python
@patch('massageProject.main_app.management.commands.populate_renkart.requests.get', side_effect=_mocked_get)
class PopulateRenkartServicesTest(TestCase):
    def test_creates_three_groups_and_ten_services(self, mock_get):
        call_command('populate_renkart')

        self.assertEqual(ServiceGroup.objects.count(), 3)
        group_names = set(ServiceGroup.objects.values_list('name_bg', flat=True))
        self.assertEqual(group_names, {
            'Портретни фотосесии', 'Fine Art фотосесии', 'Арт / Будоар фотосесии',
        })

        self.assertEqual(Service.objects.count(), 10)
        self.assertEqual(Service.objects.filter(home_page=True).count(), 3)

        mini_studio = Service.objects.get(name_bg='Мини фотосесия в студио')
        self.assertEqual(mini_studio.price, 120)
        self.assertEqual(mini_studio.group.name_bg, 'Портретни фотосесии')
        self.assertTrue(mini_studio.image.name)

        art_session = Service.objects.get(name_bg='Арт / Будоар фотосесия')
        self.assertIn('по договаряне', art_session.description_bg)
        self.assertIn('by arrangement', art_session.description_en)

    def test_services_idempotent(self, mock_get):
        call_command('populate_renkart')
        call_command('populate_renkart')

        self.assertEqual(ServiceGroup.objects.count(), 3)
        self.assertEqual(Service.objects.count(), 10)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source venv/bin/activate && python manage.py test massageProject.main_app.tests_populate_renkart.PopulateRenkartServicesTest -v 2`
Expected: FAIL — `ServiceGroup.objects.count()` is 0 (the command doesn't create services yet).

- [ ] **Step 3: Add service seeding to the command**

In `massageProject/main_app/management/commands/populate_renkart.py`, change the import block:
```python
from massageProject.main_app.models import (
    BusinessInfo, Specialist, SiteConfiguration, WorkingHours,
)
```
to:
```python
from massageProject.main_app.models import (
    BusinessInfo, Service, ServiceGroup, Specialist, SiteConfiguration, WorkingHours,
)
```

In `handle()`, change:
```python
        self._populate_site_configuration()
        self._populate_business_info(reneta_bytes)
        specialist = self._populate_specialist(reneta_bytes)
        self._populate_working_hours(specialist)

        self.stdout.write(self.style.SUCCESS("RenkArt core data populated successfully!"))
```
to:
```python
        self._populate_site_configuration()
        self._populate_business_info(reneta_bytes)
        specialist = self._populate_specialist(reneta_bytes)
        self._populate_working_hours(specialist)
        self._populate_services(reneta_bytes)

        self.stdout.write(self.style.SUCCESS("RenkArt core data populated successfully!"))
```

Add this method to the `Command` class (after `_populate_working_hours`):

```python
    def _populate_services(self, reneta_bytes):
        groups_data = [
            ('Портретни фотосесии', 'Portrait Sessions', 0),
            ('Fine Art фотосесии', 'Fine Art Portraits', 1),
            ('Арт / Будоар фотосесии', 'Art & Concept Sessions', 2),
        ]
        groups = {}
        for name_bg, name_en, order in groups_data:
            group, _created = ServiceGroup.objects.get_or_create(
                name_bg=name_bg, defaults={'name_en': name_en, 'order': order},
            )
            groups[name_bg] = group

        services_data = [
            ('Портретни фотосесии', 'Мини фотосесия в студио', 'Mini Studio Session',
             '15 обработени снимки в студийна обстановка.',
             '15 edited photos in a studio setting.',
             'Компактна студийна фотосесия за индивидуален или семеен портрет. Включва '
             '15 обработени снимки; допълнителна снимка — 10 евро (с включен 10×15см принт).',
             'A compact studio session for an individual or family portrait. Includes 15 '
             'edited photos; an extra photo is available for €10 (includes a 10×15cm print).',
             120.00, 60, True),
            ('Портретни фотосесии', 'Мини фотосесия навън', 'Mini Outdoor Session',
             '15 обработени снимки на открито.',
             '15 edited photos outdoors.',
             'Същият мини пакет, заснет на открита локация по избор. Включва 15 обработени '
             'снимки; допълнителна снимка — 10 евро (с включен 10×15см принт).',
             'The same mini package, shot at an outdoor location of your choice. Includes '
             '15 edited photos; an extra photo is available for €10 (includes a 10×15cm print).',
             130.00, 60, False),
            ('Портретни фотосесии', 'Голям фотопакет', 'Large Photo Package',
             '35 обработени снимки + подарък 20×30см арт принт.',
             '35 edited photos + a gift 20×30cm art print.',
             'Разширена фотосесия с 35 обработени снимки и подарък — арт принт 20×30см.',
             'An extended session with 35 edited photos and a gift 20×30cm art print.',
             220.00, 90, False),
            ('Портретни фотосесии', 'Макси фотопакет', 'Maxi Photo Package',
             '50 обработени снимки + подарък 20×30см арт принт.',
             '50 edited photos + a gift 20×30cm art print.',
             'Най-пълният портретен пакет — 50 обработени снимки и подарък арт принт 20×30см.',
             'Our most complete portrait package — 50 edited photos and a gift 20×30cm art print.',
             280.00, 120, False),
            ('Fine Art фотосесии', 'Fine Art фотосесия - дете', 'Fine Art Session - Child',
             'Fine Art студийна фотосесия за дете.',
             'Fine Art studio session for a child.',
             'Студийна фотосесия на чист фон, вдъхновена от класическия портрет. Включва 10 '
             'обработени снимки + архив; допълнителна снимка — 15 евро.',
             'A studio session on a plain background, inspired by classical portrait '
             'painting. Includes 10 edited photos + archive; an extra photo is €15.',
             120.00, 90, False),
            ('Fine Art фотосесии', 'Fine Art фотосесия - индивидуална', 'Fine Art Session - Individual',
             'Fine Art портрет за тийнейджъри и възрастни.',
             'Fine Art portrait for teens and adults.',
             'Индивидуален Fine Art портрет на чист фон. Включва 10 обработени снимки + '
             'архив; допълнителна снимка — 15 евро.',
             'An individual Fine Art portrait on a plain background. Includes 10 edited '
             'photos + archive; an extra photo is €15.',
             140.00, 90, True),
            ('Fine Art фотосесии', 'Fine Art фотосесия - двойка', 'Fine Art Session - Couple',
             'Fine Art портрет за двойки.',
             'Fine Art portrait for couples.',
             'Fine Art фотосесия за двама на чист фон. Включва 10 обработени снимки + '
             'архив; допълнителна снимка — 15 евро.',
             'A Fine Art session for two on a plain background. Includes 10 edited photos '
             '+ archive; an extra photo is €15.',
             160.00, 90, False),
            ('Fine Art фотосесии', 'Fine Art фотосесия - семейство', 'Fine Art Session - Family',
             'Fine Art портрет за цялото семейство.',
             'Fine Art portrait for the whole family.',
             'Fine Art фамилен портрет на чист фон. Включва 10 обработени снимки + архив; '
             'допълнителна снимка — 15 евро.',
             'A Fine Art family portrait on a plain background. Includes 10 edited photos '
             '+ archive; an extra photo is €15.',
             180.00, 90, False),
            ('Fine Art фотосесии', 'Fine Art макси пакет', 'Fine Art Maxi Package',
             '30 обработени снимки + подарък 20×30см арт принт.',
             '30 edited photos + a gift 20×30cm art print.',
             'Разширеният Fine Art пакет — 30 обработени снимки и подарък арт принт 20×30см.',
             'The extended Fine Art package — 30 edited photos and a gift 20×30cm art print.',
             280.00, 90, False),
            ('Арт / Будоар фотосесии', 'Арт / Будоар фотосесия', 'Art & Concept Session',
             'Индивидуален концептуален проект — цена по договаряне.',
             'A fully custom concept shoot — price by arrangement.',
             'Напълно индивидуална арт фотосесия с избран от Вас концепт, гардероб, '
             'аксесоари и локация. Продължителност 2–8 часа според концепцията. '
             'Посочената цена е начална — точната цена се договаря индивидуално според '
             'обхвата на проекта.',
             'A fully custom art photo session with your chosen concept, wardrobe, props, '
             'and location. Duration is 2–8 hours depending on the concept. The listed '
             "price is a starting point — the final price is agreed individually based on "
             "the project's scope.",
             150.00, 180, True),
        ]

        services = []
        for (group_name, name_bg, name_en, short_bg, short_en, desc_bg, desc_en,
             price, duration, home_page) in services_data:
            service, created = Service.objects.get_or_create(
                name_bg=name_bg,
                defaults={
                    'name_en': name_en,
                    'short_description_bg': short_bg,
                    'short_description_en': short_en,
                    'description_bg': desc_bg,
                    'description_en': desc_en,
                    'price': price,
                    'duration_in_minutes': duration,
                    'home_page': home_page,
                    'group': groups[group_name],
                }
            )
            if created:
                service.image.save('reneta.jpg', ContentFile(reneta_bytes), save=True)
                self.stdout.write(f"Created service: {service.name}")
            services.append(service)
        return services
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source venv/bin/activate && python manage.py test massageProject.main_app.tests_populate_renkart -v 2`
Expected: PASS (4/4)

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `source venv/bin/activate && python manage.py test -v 2`
Expected: PASS (196/196)

- [ ] **Step 6: Commit**

```bash
git add massageProject/main_app/management/commands/populate_renkart.py massageProject/main_app/tests_populate_renkart.py
git commit -m "feat: seed RenkArt service groups and service catalog in populate_renkart"
```

---

### Task 4: `populate_renkart` command — Gallery/Image/HomePage + BusinessWorkingHours

**Files:**
- Modify: `massageProject/main_app/management/commands/populate_renkart.py`
- Modify: `massageProject/main_app/tests_populate_renkart.py`

**Interfaces:**
- Consumes: `logo_bytes`, `reneta_bytes` (bytes, fetched in `handle()` per Task 2).
- Produces: `Command._populate_home_page(self, logo_bytes: bytes, reneta_bytes: bytes) -> HomePage` — the returned `HomePage` is consumed immediately by `_populate_business_working_hours` in this same task.
- Produces: `Command._populate_business_working_hours(self, home_page: HomePage) -> None`.

- [ ] **Step 1: Write the failing test**

Add to `massageProject/main_app/tests_populate_renkart.py` (new import + new test class):

```python
from massageProject.main_app.models import BusinessWorkingHours, HomePage
```

```python
@patch('massageProject.main_app.management.commands.populate_renkart.requests.get', side_effect=_mocked_get)
class PopulateRenkartHomePageTest(TestCase):
    def test_creates_home_page_gallery_image_and_business_hours(self, mock_get):
        call_command('populate_renkart')

        home_page = HomePage.objects.get(pk=1)
        self.assertEqual(home_page.brand_name_bg, 'RenkArt — Портретна и Арт Фотография')
        self.assertEqual(home_page.brand_name_en, 'RenkArt — Portrait & Art Photography')
        self.assertTrue(home_page.logo.name)
        self.assertEqual(home_page.gallery.images.count(), 1)
        self.assertTrue(home_page.gallery.images.first().image.name)

        self.assertEqual(BusinessWorkingHours.objects.filter(home_page=home_page).count(), 2)
        self.assertTrue(
            BusinessWorkingHours.objects.filter(
                home_page=home_page, day_label_bg='Вторник – Събота', hours_bg='10:00 - 18:00',
            ).exists()
        )

    def test_home_page_idempotent(self, mock_get):
        call_command('populate_renkart')
        call_command('populate_renkart')

        self.assertEqual(HomePage.objects.count(), 1)
        home_page = HomePage.objects.get(pk=1)
        self.assertEqual(home_page.gallery.images.count(), 1)
        self.assertEqual(BusinessWorkingHours.objects.filter(home_page=home_page).count(), 2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source venv/bin/activate && python manage.py test massageProject.main_app.tests_populate_renkart.PopulateRenkartHomePageTest -v 2`
Expected: FAIL — `HomePage.DoesNotExist` (the command doesn't create a `HomePage` yet).

- [ ] **Step 3: Add HomePage + BusinessWorkingHours seeding to the command**

In `massageProject/main_app/management/commands/populate_renkart.py`, change the import block:
```python
from massageProject.main_app.models import (
    BusinessInfo, Service, ServiceGroup, Specialist, SiteConfiguration, WorkingHours,
)
```
to:
```python
from massageProject.main_app.models import (
    BusinessInfo, BusinessWorkingHours, Gallery, GalleryImage, HomePage, Image,
    Service, ServiceGroup, Specialist, SiteConfiguration, WorkingHours,
)
```

In `handle()`, change:
```python
        self._populate_site_configuration()
        self._populate_business_info(reneta_bytes)
        specialist = self._populate_specialist(reneta_bytes)
        self._populate_working_hours(specialist)
        self._populate_services(reneta_bytes)

        self.stdout.write(self.style.SUCCESS("RenkArt core data populated successfully!"))
```
to:
```python
        self._populate_site_configuration()
        self._populate_business_info(reneta_bytes)
        specialist = self._populate_specialist(reneta_bytes)
        self._populate_working_hours(specialist)
        self._populate_services(reneta_bytes)
        home_page = self._populate_home_page(logo_bytes, reneta_bytes)
        self._populate_business_working_hours(home_page)

        self.stdout.write(self.style.SUCCESS("RenkArt core data populated successfully!"))
```

Add these two methods to the `Command` class (after `_populate_services`):

```python
    def _populate_home_page(self, logo_bytes, reneta_bytes):
        home_page = HomePage.objects.filter(pk=1).first()
        if home_page is None:
            gallery = Gallery.objects.create(title_bg='RenkArt', title_en='RenkArt')
            home_page = HomePage.objects.create(
                pk=1,
                brand_name_bg='RenkArt — Портретна и Арт Фотография',
                brand_name_en='RenkArt — Portrait & Art Photography',
                description_bg=(
                    'Добре дошли в RenkArt — където всеки кадър разказва история. '
                    'Портретна и арт фотография, вдъхновена от класическата живопис и '
                    'съвременния разказ.'
                ),
                description_en=(
                    'Welcome to RenkArt — where every frame tells a story. Portrait and '
                    'art photography inspired by classical painting and modern storytelling.'
                ),
                footer_tagline_bg='Портретна и арт фотография в Стара Загора.',
                footer_tagline_en='Portrait and art photography in Stara Zagora.',
                gallery=gallery,
            )
            home_page.logo.save('logo33.jpg', ContentFile(logo_bytes), save=True)
            self.stdout.write(f"Created home page: {home_page.brand_name}")

        if not home_page.gallery.images.exists():
            image = Image.objects.create(
                alt_text_bg='Ренета Кирилова с фотоапарат',
                alt_text_en='Reneta Kirilova with a camera',
            )
            image.image.save('reneta.jpg', ContentFile(reneta_bytes), save=True)
            GalleryImage.objects.create(gallery=home_page.gallery, image=image)
            self.stdout.write("Added hero image to gallery")

        return home_page

    def _populate_business_working_hours(self, home_page):
        rows = [
            ('Вторник – Събота', 'Tuesday – Saturday', '10:00 - 18:00', '10:00 - 18:00', 0),
            ('Неделя, Понеделник', 'Sunday, Monday', '', '', 1),
        ]
        for day_label_bg, day_label_en, hours_bg, hours_en, order in rows:
            BusinessWorkingHours.objects.get_or_create(
                home_page=home_page, day_label_bg=day_label_bg,
                defaults={
                    'day_label_en': day_label_en,
                    'hours_bg': hours_bg,
                    'hours_en': hours_en,
                    'order': order,
                },
            )
        self.stdout.write(
            "Set placeholder business hours display -- confirm real hours with the client"
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source venv/bin/activate && python manage.py test massageProject.main_app.tests_populate_renkart -v 2`
Expected: PASS (6/6)

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `source venv/bin/activate && python manage.py test -v 2`
Expected: PASS (198/198)

- [ ] **Step 6: Commit**

```bash
git add massageProject/main_app/management/commands/populate_renkart.py massageProject/main_app/tests_populate_renkart.py
git commit -m "feat: seed RenkArt home page, gallery, and business hours in populate_renkart"
```

---

### Task 5: `populate_renkart` command — Comment + Reservation demo content, full idempotency test

**Files:**
- Modify: `massageProject/main_app/management/commands/populate_renkart.py`
- Modify: `massageProject/main_app/tests_populate_renkart.py`

**Interfaces:**
- Consumes: `services` (`list[Service]`, returned by `_populate_services` per Task 3), `specialist` (`Specialist`, returned by `_populate_specialist` per Task 2).
- Produces: `Command._populate_comments(self) -> None`.
- Produces: `Command._populate_reservations(self, services: list[Service], specialist: Specialist) -> None`.

- [ ] **Step 1: Write the failing test**

Add to `massageProject/main_app/tests_populate_renkart.py` (new import + new test classes):

```python
from datetime import date

from django.contrib.auth import get_user_model
from massageProject.main_app.models import Comment, Reservation
```

```python
@patch('massageProject.main_app.management.commands.populate_renkart.requests.get', side_effect=_mocked_get)
class PopulateRenkartDemoContentTest(TestCase):
    def test_creates_comments_and_reservations(self, mock_get):
        call_command('populate_renkart')

        self.assertEqual(Comment.objects.count(), 5)
        self.assertEqual(Comment.objects.filter(is_reviewed=True).count(), 5)

        self.assertEqual(Reservation.objects.count(), 4)
        self.assertEqual(Reservation.objects.filter(status=Reservation.STATUS_COMPLETED).count(), 2)
        self.assertEqual(Reservation.objects.filter(status=Reservation.STATUS_ACTIVE).count(), 2)

        User = get_user_model()
        self.assertTrue(User.objects.filter(email='demo.client@example.com').exists())

        for reservation in Reservation.objects.filter(status=Reservation.STATUS_ACTIVE):
            self.assertNotIn(reservation.date.weekday(), (0, 6))  # closed Sun/Mon


@patch('massageProject.main_app.management.commands.populate_renkart.requests.get', side_effect=_mocked_get)
class PopulateRenkartFullIdempotencyTest(TestCase):
    def test_full_rerun_does_not_duplicate_anything(self, mock_get):
        from massageProject.main_app.models import (
            BusinessInfo, BusinessWorkingHours, Service, ServiceGroup, Specialist, WorkingHours,
        )

        call_command('populate_renkart')
        call_command('populate_renkart')

        self.assertEqual(BusinessInfo.objects.count(), 1)
        self.assertEqual(Specialist.objects.count(), 1)
        self.assertEqual(WorkingHours.objects.count(), 5)
        self.assertEqual(ServiceGroup.objects.count(), 3)
        self.assertEqual(Service.objects.count(), 10)
        self.assertEqual(HomePage.objects.count(), 1)
        self.assertEqual(BusinessWorkingHours.objects.count(), 2)
        self.assertEqual(Comment.objects.count(), 5)
        self.assertEqual(Reservation.objects.count(), 4)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source venv/bin/activate && python manage.py test massageProject.main_app.tests_populate_renkart.PopulateRenkartDemoContentTest -v 2`
Expected: FAIL — `Comment.objects.count()` is 0 (the command doesn't create demo comments/reservations yet).

- [ ] **Step 3: Add Comment + Reservation seeding to the command**

In `massageProject/main_app/management/commands/populate_renkart.py`, change the top imports:
```python
from datetime import time
```
to:
```python
from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
```

In `handle()`, change:
```python
        self._populate_services(reneta_bytes)
        home_page = self._populate_home_page(logo_bytes, reneta_bytes)
        self._populate_business_working_hours(home_page)

        self.stdout.write(self.style.SUCCESS("RenkArt core data populated successfully!"))
```
to:
```python
        services = self._populate_services(reneta_bytes)
        home_page = self._populate_home_page(logo_bytes, reneta_bytes)
        self._populate_business_working_hours(home_page)
        self._populate_comments()
        self._populate_reservations(services, specialist)

        self.stdout.write(self.style.SUCCESS("RenkArt data populated successfully!"))
        self.stdout.write(self.style.WARNING(
            "NOTE: working hours and the Art/Boudoir session price are placeholders -- "
            "confirm real values with the client before go-live."
        ))
```

Add these two methods to the `Command` class (at the end of the class):

```python
    def _populate_comments(self):
        comments_data = [
            ('Виктория Н.',
             'Фотосесията с Ренета беше невероятно преживяване! Снимките са живи, '
             'топли и много артистични.', 5),
            ('Стоян П.',
             'Професионално отношение и страхотен резултат. Препоръчвам Fine Art '
             'пакета на всеки, който търси нещо различно.', 5),
            ('Мария Д.',
             'Много благодаря за търпението по време на семейната ни фотосесия! '
             'Децата се почувстваха напълно спокойно.', 5),
            ('Георги К.',
             'Артистичната фотосесия надмина очакванията ми — истинско произведение '
             'на изкуството.', 5),
            ('Ивелина Т.',
             'Атмосферата в студиото е уютна, а Ренета има невероятно око за детайла.', 4),
        ]
        for author, content, rating in comments_data:
            comment, created = Comment.objects.get_or_create(
                author=author, content=content,
                defaults={'rating': rating, 'is_reviewed': True},
            )
            if created:
                self.stdout.write(f"Created comment by {author}")

    def _populate_reservations(self, services, specialist):
        User = get_user_model()
        user, created = User.objects.get_or_create(
            phone_number='0888920099',
            defaults={
                'email': 'demo.client@example.com',
                'first_name': 'Виктория',
                'last_name': 'Николова',
            }
        )
        if created:
            user.set_password('1234')
            user.save()

        services_by_name = {s.name: s for s in services}
        mini_studio = services_by_name['Мини фотосесия в студио']
        fine_art_couple = services_by_name['Fine Art фотосесия - двойка']
        fine_art_individual = services_by_name['Fine Art фотосесия - индивидуална']
        large_package = services_by_name['Голям фотопакет']

        today = date.today()

        def next_open_day(d):
            # Reneta is closed Sunday (6) and Monday (0)
            while d.weekday() in (0, 6):
                d += timedelta(days=1)
            return d

        reservations_data = [
            (mini_studio, today - timedelta(days=5), time(11, 0), True),
            (fine_art_couple, today - timedelta(days=2), time(14, 0), True),
            (fine_art_individual, next_open_day(today + timedelta(days=2)), time(10, 0), False),
            (large_package, next_open_day(today + timedelta(days=7)), time(15, 0), False),
        ]
        for service, d, t, is_past in reservations_data:
            defaults = {'specialist': specialist, 'additional_text': 'Очакваме сесията с нетърпение.'}
            if is_past:
                defaults['status'] = Reservation.STATUS_COMPLETED
            reservation, created = Reservation.objects.get_or_create(
                service=service, user=user, date=d, time=t, defaults=defaults,
            )
            if created:
                self.stdout.write(f"Created reservation for {service.name} on {d}")
```

Also add `Comment` and `Reservation` to the model import block — change:
```python
from massageProject.main_app.models import (
    BusinessInfo, BusinessWorkingHours, Gallery, GalleryImage, HomePage, Image,
    Service, ServiceGroup, Specialist, SiteConfiguration, WorkingHours,
)
```
to:
```python
from massageProject.main_app.models import (
    BusinessInfo, BusinessWorkingHours, Comment, Gallery, GalleryImage, HomePage,
    Image, Reservation, Service, ServiceGroup, Specialist, SiteConfiguration,
    WorkingHours,
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source venv/bin/activate && python manage.py test massageProject.main_app.tests_populate_renkart -v 2`
Expected: PASS (8/8)

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `source venv/bin/activate && python manage.py test -v 2`
Expected: PASS (200/200)

- [ ] **Step 6: Commit**

```bash
git add massageProject/main_app/management/commands/populate_renkart.py massageProject/main_app/tests_populate_renkart.py
git commit -m "feat: seed RenkArt demo comments and reservations in populate_renkart"
```

---

### Task 6: Translation catalog regeneration

**Files:**
- Modify: `locale/bg/LC_MESSAGES/django.po`, `locale/bg/LC_MESSAGES/django.mo`
- Modify: `locale/en/LC_MESSAGES/django.po`, `locale/en/LC_MESSAGES/django.mo`

**Interfaces:**
- Consumes: nothing from prior tasks' code — this task only regenerates i18n catalogs to reflect Task 1's template text change. Tasks 2-5 (the `populate_renkart` command) introduce zero new gettext msgids — all their content is DB data via modeltranslation, a separate mechanism from the `.po`/`.mo` catalogs (confirmed no `{% trans %}`/`gettext` usage was added by those tasks).

- [ ] **Step 1: Regenerate the message catalogs**

Run:
```bash
source venv/bin/activate
python manage.py makemessages -l bg -l en
```
Expected: a new msgid `€` appears in both `locale/bg/LC_MESSAGES/django.po` and `locale/en/LC_MESSAGES/django.po`, referencing all 6 template lines changed in Task 1. The old `лв`/`лв.` entries are marked `#~` (obsolete), not deleted.

- [ ] **Step 2: Fill in the new translation**

In `locale/bg/LC_MESSAGES/django.po`, find the new entry:
```
msgid "€"
msgstr ""
```
and set:
```
msgid "€"
msgstr "€"
```

In `locale/en/LC_MESSAGES/django.po`, find the same new entry and set:
```
msgid "€"
msgstr "€"
```

- [ ] **Step 3: Verify no other msgid is left blank by this change**

Run:
```bash
source venv/bin/activate
python -c "
import polib
for lang in ('bg', 'en'):
    po = polib.pofile(f'locale/{lang}/LC_MESSAGES/django.po')
    entry = po.find('€')
    assert entry is not None, f'{lang}: missing entry'
    assert entry.msgstr == '€', f'{lang}: unexpected msgstr {entry.msgstr!r}'
    assert not entry.fuzzy, f'{lang}: entry is fuzzy'
print('OK')
"
```
Expected: `OK`

- [ ] **Step 4: Compile the catalogs**

Run:
```bash
source venv/bin/activate
python manage.py compilemessages
```
Expected: `processing file django.po in .../locale/bg/LC_MESSAGES` and the same for `en`, no errors.

- [ ] **Step 5: Run the full test suite**

Run: `source venv/bin/activate && python manage.py test -v 2`
Expected: PASS (200/200)

- [ ] **Step 6: Commit**

```bash
git add locale/bg/LC_MESSAGES/django.po locale/bg/LC_MESSAGES/django.mo locale/en/LC_MESSAGES/django.po locale/en/LC_MESSAGES/django.mo
git commit -m "chore: regenerate translation catalogs after currency label change"
```

---

## Manual steps after all tasks complete (not part of the TDD task cycle)

These are one-time local actions for the person previewing the RenkArt site — not something a task's automated tests exercise, since Django's test suite always runs against an isolated test database regardless of `DATABASE_URL`.

1. Create the new local database (same Postgres role already used for `massage_db`):
   ```bash
   createdb -U signal -h localhost renkart_db
   ```
2. To preview RenkArt: edit `.env`'s `DATABASE_URL` to
   `postgres://signal:ialangis@localhost:5432/renkart_db`, then run:
   ```bash
   source venv/bin/activate
   python manage.py migrate
   python manage.py populate_renkart
   python manage.py runserver
   ```
3. To go back to the massage business site: edit `.env`'s `DATABASE_URL` back to
   `postgres://signal:ialangis@localhost:5432/massage_db`.

## Out of scope (unchanged from the design spec)

News/seasonal campaign content, Part 3 deployment infra, the remaining ~15-18 curated portfolio photos beyond the 2 already confirmed downloadable, and any relabeling of massage-domain vocabulary in code.

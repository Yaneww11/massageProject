# Terminology Template Interpolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the remaining hardcoded massage-domain vocabulary in templates
(`масаж`/`масажист`) respond to `SiteConfiguration.service_singular` /
`.service_plural` / `.specialist_singular` / `.specialist_plural` (from Plan
A), so a non-massage brand's site doesn't say "Масажист" ("Masseur") in its
booking flow.

**Architecture:** Template-only changes. Two policies, per the already-
approved design doc (`docs/superpowers/specs/2026-07-19-white-label-platform-
design.md`, section 2c): (1) a domain term that stands alone as a label/
heading gets replaced with `{{ site_config.<field>|capfirst }}`; (2) a domain
term embedded in a composed sentence or JS message (where per-language word
order or Bulgarian declension would break) gets rewritten in fully generic
Bulgarian with the term dropped entirely, not interpolated — mirroring the
design doc's own worked example ("Запази час за масаж" → "Запази час").

**Tech Stack:** Django template language only — no new views, no new model
fields (`site_config` and its 4 terminology fields already exist from Plan A
and are already in every template's context).

## Global Constraints

- This is Plan C of the 4-plan split of Part 2 ("Brand Configuration"),
  building on Plan A (`SiteConfiguration` model) and Plan B (theme
  mechanics), both already merged.
- Model `verbose_name`s in `massageProject/main_app/models.py` (`_('Масаж')`,
  `_('Терапевт')`, etc.) are explicitly **out of scope** — the project owner
  decided to leave those as-is; only template-rendered, user-facing copy
  changes in this plan.
- Do not touch `massageProject/main_app/views.py`, `forms.py`, `admin.py`,
  or any model — this plan only edits `.html` template files.
- Every string this plan rewrites (the "generic, drop the term" category)
  must remain grammatically natural standalone Bulgarian — not a literal
  word-for-word deletion that reads broken.
- Per CLAUDE.md, this plan introduces several brand-new `msgid`s (the
  rewritten generic strings are different text from the old ones, not
  reusable); the final task must run `makemessages`/`compilemessages` and
  supply real bg/en translations for every one of them.
- Do not change `home.css`, `variables.css`, or anything from Plan B — this
  plan is templates only.

---

### Task 1: Footer and hero branding — drop the domain word

**Files:**
- Modify: `templates/partials/footer.html`
- Modify: `templates/partials/hero/split.html`
- Test: `massageProject/main_app/tests_terminology.py` (new file)

**Interfaces:**
- Consumes: `brand_name` (already in every template's context via Plan A's
  `admin_branding` context processor — unrelated to `site_config`, do not
  confuse the two).
- Produces: nothing new — pure template text changes.

- [ ] **Step 1: Write the failing tests**

Create `massageProject/main_app/tests_terminology.py`:

```python
from django.test import TestCase


class FooterBrandingTest(TestCase):
    def test_footer_copyright_uses_dynamic_brand_name_not_hardcoded_text(self):
        response = self.client.get('/bg/')
        content = response.content.decode()
        self.assertNotIn('Масажно студио Сияние', content)
        self.assertIn('Relax &amp; Health', content)  # demo HomePage.brand_name default


class HeroBrandingTest(TestCase):
    def test_hero_eyebrow_does_not_say_massage_studio(self):
        response = self.client.get('/bg/')
        content = response.content.decode()
        self.assertNotIn('Масажно студио · от 2014', content)
        self.assertIn('Нашето студио · от 2014', content)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test massageProject.main_app.tests_terminology -v 2`
Expected: FAIL — footer still contains "Масажно студио Сияние" and hero
still contains "Масажно студио · от 2014".

- [ ] **Step 3: Fix the footer**

In `templates/partials/footer.html`, change:

```html
            <p>&copy; 2026 {% trans "Масажно студио Сияние" %}</p>
```

to:

```html
            <p>&copy; 2026 {{ brand_name }}</p>
```

- [ ] **Step 4: Fix the hero eyebrow and image alt fallback**

In `templates/partials/hero/split.html`, change:

```html
            <span class="hp-eyebrow">{% trans "Масажно студио · от 2014" %}</span>
```

to:

```html
            <span class="hp-eyebrow">{% trans "Нашето студио · от 2014" %}</span>
```

and change:

```html
            <img src="{% static 'images/home_background.jpg' %}" alt="{% if page %}{{ page.brand_name }}{% else %}{% trans "Масажно студио" %}{% endif %}">
```

to:

```html
            <img src="{% static 'images/home_background.jpg' %}" alt="{% if page %}{{ page.brand_name }}{% else %}{% trans "Нашето студио" %}{% endif %}">
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python manage.py test massageProject.main_app.tests_terminology -v 2`
Expected: PASS — both tests green.

- [ ] **Step 6: Commit**

```bash
git add templates/partials/footer.html templates/partials/hero/split.html \
        massageProject/main_app/tests_terminology.py
git commit -m "fix: replace hardcoded massage-studio branding text with dynamic/generic copy"
```

---

### Task 2: Standalone term interpolation — home heading, services subtitle, profile role label

**Files:**
- Modify: `templates/pages/home.html`
- Modify: `templates/pages/services_page.html`
- Modify: `templates/pages/my_profile.html`
- Test: `massageProject/main_app/tests_terminology.py` (append)

**Interfaces:**
- Consumes: `site_config.service_plural`, `site_config.specialist_singular`
  (Plan A, already in every template's context).

- [ ] **Step 1: Write the failing tests**

Append to `massageProject/main_app/tests_terminology.py`:

```python
class HomeServicesHeadingTest(TestCase):
    def test_home_featured_services_heading_uses_service_plural(self):
        response = self.client.get('/bg/')
        content = response.content.decode()
        self.assertNotIn('Предпочитани масажи', content)
        self.assertIn('Предпочитани услуги', content)  # default service_plural


class ServicesPageSubtitleTest(TestCase):
    def test_services_page_subtitle_does_not_say_massage_procedures(self):
        response = self.client.get('/bg/services/')
        content = response.content.decode()
        self.assertNotIn('масажни процедури', content)
        self.assertIn('нашите услуги', content)


class ProfileSpecialistRoleLabelTest(TestCase):
    def test_next_booking_specialist_role_uses_specialist_singular(self):
        from datetime import date, time, timedelta
        from django.contrib.auth import get_user_model
        from massageProject.main_app.models import Service, Specialist, WorkingHours, Reservation

        User = get_user_model()
        user = User.objects.create_user(
            phone_number='0888111222', email='profiletest@example.com',
            password='testpass123', first_name='Test', last_name='User',
        )
        specialist = Specialist.objects.create(
            name='Test Specialist', description='desc', phone_number='0888111222',
            email='specialist@example.com',
        )
        service = Service.objects.create(
            name='Test Service', description='desc', price=50, duration_in_minutes=60,
            short_description='short',
        )
        WorkingHours.objects.create(
            specialist=specialist, day_of_week=(date.today() + timedelta(days=2)).weekday(),
            start_time=time(9, 0), end_time=time(18, 0),
        )
        Reservation.objects.create(
            service=service, specialist=specialist, user=user,
            date=date.today() + timedelta(days=2), time=time(10, 0),
        )
        self.client.force_login(user)
        response = self.client.get('/bg/profile/')
        content = response.content.decode()
        self.assertNotIn('>Масажист<', content)
        self.assertIn('>Специалист<', content)  # default specialist_singular, capitalized
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test massageProject.main_app.tests_terminology -v 2`
Expected: FAIL on all 3 new tests — old hardcoded strings still present.

- [ ] **Step 3: Fix the home page heading**

In `templates/pages/home.html`, change:

```html
            <h2 class="hp-section-title">{% trans "Предпочитани масажи" %}</h2>
```

to:

```html
            <h2 class="hp-section-title">{% trans "Предпочитани" %} {{ site_config.service_plural }}</h2>
```

- [ ] **Step 4: Fix the services page subtitle**

In `templates/pages/services_page.html`, change:

```html
      <p class="svc-hero__sub">{% trans "Открийте пълния списък с нашите масажни процедури — всяка е съобразена с вашето тяло и нужди." %}</p>
```

to:

```html
      <p class="svc-hero__sub">{% trans "Открийте пълния списък с нашите услуги — всяка е съобразена с вашето тяло и нужди." %}</p>
```

- [ ] **Step 5: Fix the profile page specialist role label**

In `templates/pages/my_profile.html`, change:

```html
            <span class="specialist-role">{% trans "Масажист" %}</span>
```

to:

```html
            <span class="specialist-role">{{ site_config.specialist_singular|capfirst }}</span>
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python manage.py test massageProject.main_app.tests_terminology -v 2`
Expected: PASS — all tests green.

- [ ] **Step 7: Commit**

```bash
git add templates/pages/home.html templates/pages/services_page.html \
        templates/pages/my_profile.html massageProject/main_app/tests_terminology.py
git commit -m "feat: interpolate service/specialist terminology into standalone headings and labels"
```

---

### Task 3: Booking wizard (`reservation.html`) — step labels, summary labels, JS messages

**Files:**
- Modify: `templates/pages/reservation.html`
- Test: `massageProject/main_app/tests_terminology.py` (append)

**Interfaces:**
- Consumes: `site_config.service_singular`, `site_config.specialist_singular`.

- [ ] **Step 1: Write the failing test**

Append to `massageProject/main_app/tests_terminology.py`:

```python
class ReservationPageTerminologyTest(TestCase):
    def test_reservation_page_labels_use_terminology_not_massage(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.create_user(
            phone_number='0888333444', email='reservationtest@example.com',
            password='testpass123', first_name='Test', last_name='User',
        )
        self.client.force_login(user)
        response = self.client.get('/bg/reserve/')
        content = response.content.decode()
        self.assertNotIn('>Масаж<', content)
        self.assertNotIn('>Масажист<', content)
        self.assertIn('>Услуга<', content)  # default service_singular, capitalized
        self.assertIn('>Специалист<', content)  # default specialist_singular, capitalized
        self.assertNotIn('Моля, изберете масаж, масажист и дата.', content)
        self.assertNotIn('Типът масаж беше променен', content)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test massageProject.main_app.tests_terminology.ReservationPageTerminologyTest -v 2`
Expected: FAIL — old hardcoded strings still present.

- [ ] **Step 3: Replace the 6 standalone label occurrences**

In `templates/pages/reservation.html`, make these 6 replacements (each
occurs once, in this order top to bottom in the file):

Change (line ~30):
```html
          <div class="bn-step-label">{% trans "Масаж" %}</div>
```
to:
```html
          <div class="bn-step-label">{{ site_config.service_singular|capfirst }}</div>
```

Change (line ~49):
```html
          <div class="bn-step-label">{% trans "Масажист" %}</div>
```
to:
```html
          <div class="bn-step-label">{{ site_config.specialist_singular|capfirst }}</div>
```

Change (line ~163):
```html
            <span>{% trans "Масаж" %}</span><span id="s-svc">—</span>
```
to:
```html
            <span>{{ site_config.service_singular|capfirst }}</span><span id="s-svc">—</span>
```

Change (line ~166):
```html
            <span>{% trans "Масажист" %}</span><span id="s-thp">—</span>
```
to:
```html
            <span>{{ site_config.specialist_singular|capfirst }}</span><span id="s-thp">—</span>
```

Change (line ~212):
```html
      <div class="bn-summary-row"><span>{% trans "Масаж" %}</span><span id="conf-svc"></span></div>
```
to:
```html
      <div class="bn-summary-row"><span>{{ site_config.service_singular|capfirst }}</span><span id="conf-svc"></span></div>
```

Change (line ~213):
```html
      <div class="bn-summary-row"><span>{% trans "Масажист" %}</span><span id="conf-thp"></span></div>
```
to:
```html
      <div class="bn-summary-row"><span>{{ site_config.specialist_singular|capfirst }}</span><span id="conf-thp"></span></div>
```

- [ ] **Step 4: Rewrite the 2 composed JS messages generically**

In `templates/pages/reservation.html`, change:

```javascript
  const MSG_SELECT_FIRST   = "{% trans 'Моля, изберете масаж, масажист и дата.' %}";
```
to:
```javascript
  const MSG_SELECT_FIRST   = "{% trans 'Моля, попълнете всички полета по-горе, преди да продължите.' %}";
```

and change:

```javascript
  const MSG_SERVICE_CHANGED= "{% trans 'Типът масаж беше променен. Моля, изберете нов час.' %}";
```
to:
```javascript
  const MSG_SERVICE_CHANGED= "{% trans 'Вашият избор беше променен. Моля, изберете нов час.' %}";
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python manage.py test massageProject.main_app.tests_terminology -v 2`
Expected: PASS — all tests green.

- [ ] **Step 6: Run the full test suite**

Run: `python manage.py test -v 2`
Expected: PASS — no regressions (this template also has JS-side logic
untouched by these text-only changes).

- [ ] **Step 7: Commit**

```bash
git add templates/pages/reservation.html massageProject/main_app/tests_terminology.py
git commit -m "feat: interpolate terminology and genericize copy in the booking wizard"
```

---

### Task 4: Edit/delete reservation pages — labels and JS message

**Files:**
- Modify: `templates/reservation/edit-reservation.html`
- Modify: `templates/reservation/delete-reservation.html`
- Test: `massageProject/main_app/tests_terminology.py` (append)

**Interfaces:**
- Consumes: `site_config.service_singular`, `site_config.specialist_singular`.

- [ ] **Step 1: Write the failing test**

Append to `massageProject/main_app/tests_terminology.py`:

```python
class EditDeleteReservationTerminologyTest(TestCase):
    def _make_reservation(self):
        from datetime import date, time, timedelta
        from django.contrib.auth import get_user_model
        from massageProject.main_app.models import Service, Specialist, WorkingHours, Reservation

        User = get_user_model()
        user = User.objects.create_user(
            phone_number='0888555666', email='editdeletetest@example.com',
            password='testpass123', first_name='Test', last_name='User',
        )
        specialist = Specialist.objects.create(
            name='Test Specialist 2', description='desc', phone_number='0888555666',
            email='specialist2@example.com',
        )
        service = Service.objects.create(
            name='Test Service 2', description='desc', price=50, duration_in_minutes=60,
            short_description='short',
        )
        WorkingHours.objects.create(
            specialist=specialist, day_of_week=(date.today() + timedelta(days=5)).weekday(),
            start_time=time(9, 0), end_time=time(18, 0),
        )
        reservation = Reservation.objects.create(
            service=service, specialist=specialist, user=user,
            date=date.today() + timedelta(days=5), time=time(10, 0),
        )
        self.client.force_login(user)
        return reservation

    def test_edit_reservation_page_uses_terminology(self):
        reservation = self._make_reservation()
        response = self.client.get(f'/{reservation.pk}/edit_reserve/')
        content = response.content.decode()
        self.assertNotIn('Тип масаж', content)
        self.assertNotIn('>Масажист<', content)
        self.assertIn('>Услуга<', content)
        self.assertIn('>Специалист<', content)
        self.assertNotIn('Моля, първо изберете тип масаж, масажист и дата.', content)

    def test_delete_reservation_page_uses_terminology(self):
        reservation = self._make_reservation()
        response = self.client.get(f'/{reservation.pk}/delete_reserve/')
        content = response.content.decode()
        self.assertNotIn('Тип масаж', content)
        self.assertNotIn('>Масажист<', content)
        self.assertIn('>Услуга<', content)
        self.assertIn('>Специалист<', content)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test massageProject.main_app.tests_terminology.EditDeleteReservationTerminologyTest -v 2`
Expected: FAIL — old hardcoded strings still present.

- [ ] **Step 3: Fix `edit-reservation.html`**

Change:
```html
                <label for="service">{% trans "Тип масаж" %}</label>
```
to:
```html
                <label for="service">{{ site_config.service_singular|capfirst }}</label>
```

Change:
```html
                <label for="specialist">{% trans "Масажист" %}</label>
```
to:
```html
                <label for="specialist">{{ site_config.specialist_singular|capfirst }}</label>
```

Change:
```javascript
    const MSG_SELECT_FIRST = "{% trans 'Моля, първо изберете тип масаж, масажист и дата.' %}";
```
to:
```javascript
    const MSG_SELECT_FIRST = "{% trans 'Моля, попълнете всички полета по-горе, преди да продължите.' %}";
```

- [ ] **Step 4: Fix `delete-reservation.html`**

Change:
```html
                <label for="service">{% trans "Тип масаж" %}</label>
```
to:
```html
                <label for="service">{{ site_config.service_singular|capfirst }}</label>
```

Change:
```html
                <label for="specialist">{% trans "Масажист" %}</label>
```
to:
```html
                <label for="specialist">{{ site_config.specialist_singular|capfirst }}</label>
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python manage.py test massageProject.main_app.tests_terminology -v 2`
Expected: PASS — all tests green.

- [ ] **Step 6: Run the full test suite**

Run: `python manage.py test -v 2`
Expected: PASS — no regressions.

- [ ] **Step 7: Commit**

```bash
git add templates/reservation/edit-reservation.html templates/reservation/delete-reservation.html \
        massageProject/main_app/tests_terminology.py
git commit -m "feat: interpolate terminology in edit/delete reservation pages"
```

---

### Task 5: Full regression + i18n regeneration

**Files:**
- No new source files.
- Modify: `locale/bg/LC_MESSAGES/django.po`, `locale/bg/LC_MESSAGES/django.mo`
- Modify: `locale/en/LC_MESSAGES/django.po`, `locale/en/LC_MESSAGES/django.mo`

**Interfaces:**
- Consumes: everything from Tasks 1-4.

- [ ] **Step 1: Run the full test suite**

Run: `python manage.py test -v 2`
Expected: PASS — every test in the project passes (Plan A + Plan B tests,
plus this plan's new `tests_terminology.py`).

- [ ] **Step 2: Regenerate message catalogs**

```bash
source venv/bin/activate
python manage.py makemessages -l bg -l en
```

This plan introduced these brand-new `msgid`s (all previous ones they
replace — "Масажно студио Сияние", "Масажно студио · от 2014", "Масажно
студио", "Предпочитани масажи", the old services subtitle, "Масаж", "Тип
масаж", the two old JS messages, "Моля, първо изберете тип масаж, масажист
и дата." — become orphaned/unused msgids that `makemessages` will mark
obsolete with a leading `#~`, which is expected and correct, not something to
undo). Fill in `msgstr` for both `locale/bg/LC_MESSAGES/django.po` and
`locale/en/LC_MESSAGES/django.po` for each of these new msgids:

| msgid (bg, source) | bg msgstr | en msgstr |
|---|---|---|
| `Нашето студио · от 2014` | `Нашето студио · от 2014` | `Our studio · since 2014` |
| `Нашето студио` | `Нашето студио` | `Our studio` |
| `Предпочитани` | `Предпочитани` | `Preferred` |
| `Открийте пълния списък с нашите услуги — всяка е съобразена с вашето тяло и нужди.` | (same, verbatim) | `Discover our full list of services — each tailored to your body and needs.` |
| `Моля, попълнете всички полета по-горе, преди да продължите.` | (same, verbatim) | `Please fill in all the fields above before continuing.` |
| `Вашият избор беше променен. Моля, изберете нов час.` | (same, verbatim) | `Your selection has changed. Please choose a new time.` |

`{{ brand_name }}` and `{{ site_config.service_plural }}` etc. are template
variables, not `{% trans %}` strings, so they do not appear in the `.po`
files at all — only the literal `{% trans %}` strings above do.

- [ ] **Step 3: Compile messages**

```bash
python manage.py compilemessages
```

- [ ] **Step 4: Commit**

```bash
git add locale/bg/LC_MESSAGES/django.po locale/bg/LC_MESSAGES/django.mo \
        locale/en/LC_MESSAGES/django.po locale/en/LC_MESSAGES/django.mo
git commit -m "chore: regenerate translation catalogs after terminology template changes"
```

---

## Plan Self-Review Notes

- **Spec coverage:** every hardcoded `масаж`/`масажист` occurrence found by
  `grep -rniE "масаж|терапевт" templates/` (excluding `models.py`, out of
  scope per the project owner's decision) is addressed: footer + hero (Task
  1), home heading + services subtitle + profile role (Task 2), booking
  wizard (Task 3), edit/delete reservation (Task 4). i18n regenerated (Task
  5).
- **Placeholder scan:** no TBD/TODO; every step has literal before/after
  template snippets.
- **Type consistency:** `site_config.service_singular`/`.service_plural`/
  `.specialist_singular`/`.specialist_plural` are the exact field names Plan
  A defined on `SiteConfiguration` — verified consistent across all 4 tasks,
  no typos or alternate names introduced.

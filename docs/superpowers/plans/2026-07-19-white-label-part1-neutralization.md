# White-Label Part 1: Neutralization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename every massage-specific code identifier (models, fields, views, URLs, templates, CSS hooks) to business-neutral terms, with zero behavior or wording change.

**Architecture:** Pure rename refactor executed in dependency-safe slices: one slice per domain term (massage→service, masseur→specialist), then the model-class renames, then the public URL/template-file renames, then a final sweep. The full test suite must pass after every task. Migrations must be `RenameModel`/`RenameField`, never Delete+Create.

**Tech Stack:** Django 5, django-modeltranslation, SQLite (dev), existing test suite via `python manage.py test`.

**Spec:** `docs/superpowers/specs/2026-07-19-white-label-platform-design.md` (Part 1 section — the rename map there is the contract).

## Global Constraints

- Activate the venv before every command: `source venv/bin/activate`.
- The Django package name `massageProject` stays — never rename it or its imports (owner decision).
- User-visible wording stays unchanged: Bulgarian strings (`"Масаж"`, `"Терапевт"`, `verbose_name`s, validation messages, `{% trans %}` literals) and `populate_db` sample-data text (e.g. `'Swedish Massage'`) are NOT reworded. Only code identifiers change. Two deliberate exceptions, both in Task 6: the hardcoded `<title>Massage Center</title>` and minor English-only strings noted there.
- Deferred to Part 2 (do NOT touch): `admin.site.site_header = "Massage Studio Administration"` in `massageProject/urls.py`; neutralizing Bulgarian `verbose_name` wording.
- The permission string `'main_app.view_all_reservations'` is a hand-written literal, not derived from a model name — it stays exactly as is.
- Every migration created in this plan must contain only `RenameModel`, `RenameField`, and `AlterField` (for `upload_to` changes) operations. If `makemigrations` produces `DeleteModel`/`CreateModel` or `RemoveField`/`AddField`, STOP — you answered a rename prompt wrong; delete the migration file and redo.
- `makemigrations` will ask interactive questions like `Was the model main_app.Massage renamed to Service? [y/N]` — always answer `y`.
- Dev database data is disposable (spec: nothing deployed). If image paths break after `upload_to` changes, re-seed: `python manage.py flush --noinput && python manage.py migrate && python manage.py populate_db`.
- The suffixed sed rules (`massage_id`, `massages_data`, `masseur-`) must run BEFORE the bare word-boundary rules in every sed invocation — the order given in each task is mandatory.
- `sed` word boundaries protect the package name: `\bmassage\b` does not match `massageProject`. After every sed, review `git diff` before committing.

---

### Task 1: Baseline and branch

**Files:**
- No file changes; creates branch `white-label-part1`.

**Interfaces:**
- Consumes: current green test suite on `main`.
- Produces: branch `white-label-part1`; recorded baseline test count that Tasks 2–6 must preserve.

- [ ] **Step 1: Create the branch**

```bash
cd /home/yaneyan/pycharmProjects/yane/massageProject
git checkout -b white-label-part1
```

- [ ] **Step 2: Run the full suite and record the baseline**

Run: `source venv/bin/activate && python manage.py test 2>&1 | tail -5`
Expected: `OK` and a line `Ran N tests` — write N down; every later task must end with the same N (or higher, never lower) and `OK`.

If the suite is not green on `main`, STOP and report — do not start the refactor on a broken baseline.

---

### Task 2: Rename massage → service (model, fields, params, context vars)

**Files:**
- Modify: `massageProject/main_app/models.py`
- Modify: `massageProject/main_app/translation.py`
- Modify: `massageProject/main_app/forms.py`
- Modify: `massageProject/main_app/views.py`
- Modify: `massageProject/main_app/admin.py`
- Modify: `massageProject/settings.py` (one Unfold sidebar link)
- Modify: `massageProject/main_app/management/commands/populate_db.py` (manual edit — contains sample-data strings)
- Modify: `templates/pages/home.html`, `templates/partials/featured_with_image.html`, `templates/partials/featured_without_image.html`, `templates/pages/massages_page.html`, `templates/pages/massage_detail.html`, `templates/pages/reservation.html`, `templates/reservation/edit-reservation.html`, `templates/reservation/delete-reservation.html`, `templates/pages/my_profile.html`
- Create: `massageProject/main_app/migrations/0020_*.py` (generated)
- Test: existing suite — `massageProject/main_app/tests.py`, `tests_bug_fixes.py` (renamed identifiers inside them)

**Interfaces:**
- Consumes: baseline from Task 1.
- Produces: model `Service` (was `Massage`); FK field `MessageReservation.service` (was `.massage`); `ServiceGroup` reverse accessor `services` (was `massages`); view classes `ServicesDashboard`, `ServiceDetail` (was `MassagesDashboard`, `MassageDetail`); `check_availability` GET param `service_id` (was `massage_id`); template context vars `services`, `services_data`, `service`; form field `service`; admin class `ServiceAdmin`. URL names/paths and template filenames are NOT touched (Task 5).

- [ ] **Step 1: Apply the identifier renames to the Python files (except populate_db)**

```bash
sed -i -E '
  s/MassagesDashboard/ServicesDashboard/g;
  s/MassageDetail/ServiceDetail/g;
  s/MassageAdmin/ServiceAdmin/g;
  s/MassageTranslationOptions/ServiceTranslationOptions/g;
  s/main_app_massage_changelist/main_app_service_changelist/g;
  s/massages_data/services_data/g;
  s/massage_id/service_id/g;
  s/\bMassage\b/Service/g;
  s/\bmassages\b/services/g;
  s/\bmassage\b/service/g;
' massageProject/main_app/models.py \
  massageProject/main_app/translation.py \
  massageProject/main_app/forms.py \
  massageProject/main_app/views.py \
  massageProject/main_app/admin.py \
  massageProject/main_app/urls.py \
  massageProject/settings.py \
  massageProject/main_app/tests.py \
  massageProject/main_app/tests_bug_fixes.py
```

Note: `massageProject/main_app/urls.py` is included only so its `from ... import MassagesDashboard, MassageDetail` line follows the class rename — the URL paths/names in it contain `massages/`/`massage/` as path strings and `massages_dashboard`/`massage_detail` as names, which the word-boundary rules do NOT match (underscore/slash-adjacent). Verify in the diff that only the import line changed in `urls.py`.

- [ ] **Step 2: Review the diff for collateral damage**

Run: `git diff massageProject/ | grep -E '^[+-].*(Масаж|масаж)' | head`
Expected: verbose_name/validation-message lines may appear as changed lines ONLY if the same line also contained a renamed identifier; the Cyrillic wording itself must be identical on the `-` and `+` lines. Also confirm:

Run: `git diff massageProject/settings.py`
Expected: exactly one changed line — `main_app_massage_changelist` → `main_app_service_changelist`.

- [ ] **Step 3: Verify the key model lines look like this**

`massageProject/main_app/models.py` must now contain:

```python
class Service(models.Model):
    ...
    image = models.ImageField(upload_to='massages/')   # upload_to changed in Step 4
    ...
        related_name='services',
```

and in `MessageReservation` (class name unchanged until Task 4):

```python
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name='reservations'
    )
```

and `clean()` accessing `self.service_id`, `self.service.duration_in_minutes`, `__str__` using `self.service.name`.

- [ ] **Step 4: Change the upload path**

In `massageProject/main_app/models.py`, change:

```python
    image = models.ImageField(upload_to='massages/')
```
to:
```python
    image = models.ImageField(upload_to='services/')
```

- [ ] **Step 5: Manually edit populate_db.py**

Open `massageProject/main_app/management/commands/populate_db.py`. Rename identifiers ONLY — the sample-data strings (`'Swedish Massage'`, descriptions mentioning massage) stay verbatim:

- `from massageProject.main_app.models import (Massage, ...)` → `(Service, ...)`
- variable `massages_data` → `services_data`, `massages` → `services`, loop var `massage` → `service`
- `Massage.objects.get_or_create(` → `Service.objects.get_or_create(`
- any `massage=` keyword arguments to reservation creation → `service=`
- image path strings under `'massages/...'` → `'services/...'`

Run: `grep -nE '\bMassage\b|massages_data|Massage\.objects' massageProject/main_app/management/commands/populate_db.py`
Expected: no output (matches inside quoted sample-text strings like `'Swedish Massage'` are allowed — check each remaining hit is inside a string literal; identifier hits are a failure).

- [ ] **Step 6: Apply the renames to the templates**

```bash
sed -i -E '
  s/massages-data/services-data/g;
  s/massages_data/services_data/g;
  s/massage_id/service_id/g;
  s/massageId/serviceId/g;
  s/id_massage/id_service/g;
  s/\bmassages\b/services/g;
  s/\bmassage\b/service/g;
' templates/pages/home.html \
  templates/partials/featured_with_image.html \
  templates/partials/featured_without_image.html \
  templates/pages/massages_page.html \
  templates/pages/massage_detail.html \
  templates/pages/reservation.html \
  templates/reservation/edit-reservation.html \
  templates/reservation/delete-reservation.html \
  templates/pages/my_profile.html
```

Then review `git diff templates/` and confirm:
- `{% url 'massage_detail' %}` and `{% url 'massages_dashboard' %}` references are UNCHANGED (URL names keep their old spelling until Task 5 — the word-boundary rules cannot touch them because of the `_`).
- `?massage={{ m.pk }}` became `?service={{ m.pk }}` (matches the `request.GET.get('service')` rename in views).
- `{{ services_data|json_script:"services-data" }}` and the JS `getElementById('services-data')` (or equivalent) agree.
- JS fetch calls now send `service_id=`.
- Form field references now use `id_service` (the form field rename changes the rendered input id/name automatically).
- Cyrillic labels (`Тип масаж` etc.) are untouched.

- [ ] **Step 7: Generate and inspect the migration**

Run: `python manage.py makemigrations main_app`
Answer `y` to every rename question (`Was the model main_app.Massage renamed to Service?`, `Was messagereservation.massage renamed to messagereservation.service?`).

Then: `cat massageProject/main_app/migrations/0020_*.py`
Expected operations ONLY: `migrations.RenameModel(old_name='Massage', new_name='Service')`, `migrations.RenameField(model_name='messagereservation', old_name='massage', new_name='service')`, `migrations.AlterField(...)` entries (upload_to and FK retarget/related_name). Any `CreateModel`/`DeleteModel`: delete the file and redo Step 7.

Run: `python manage.py migrate`
Expected: `OK` / `Applying main_app.0020_... OK`

- [ ] **Step 8: Rename the media directory and re-seed**

```bash
[ -d media/massages ] && mv media/massages media/services
python manage.py flush --noinput && python manage.py migrate && python manage.py populate_db
```
Expected: populate_db completes without errors.

- [ ] **Step 9: Run the full suite**

Run: `python manage.py test 2>&1 | tail -3`
Expected: `OK`, `Ran N tests` with N = baseline from Task 1.

- [ ] **Step 10: Residual grep**

Run: `grep -rnE '\bMassage\b|\bmassage\b|\bmassages\b' massageProject/ templates/ --include='*.py' --include='*.html' | grep -v __pycache__ | grep -v migrations/00 | grep -vE "massages?_dashboard|massage_detail|massages?/|masseur"`
Expected: only hits that are (a) inside quoted sample-data/wording strings, (b) the deferred `site_header`, (c) the `<title>` in base.html (Task 6), (d) URL path strings and template filenames (Task 5). Anything else: fix before committing.

- [ ] **Step 11: Commit**

```bash
git add -A
git commit -m "refactor: rename Massage to Service across models, views, forms, admin, templates"
```

---

### Task 3: Rename masseur → specialist (model, fields, params, CSS hooks)

**Files:**
- Modify: `massageProject/main_app/models.py` (`Masseur` model, `WorkingHours.masseur`, `MessageReservation.masseur`, `upload_to='masseurs/'`)
- Modify: `massageProject/main_app/translation.py`, `forms.py`, `views.py`, `admin.py`
- Modify: `massageProject/settings.py` (sidebar link `main_app_masseur_changelist`)
- Modify: `massageProject/main_app/management/commands/populate_db.py` (manual edit)
- Modify: `massageProject/main_app/tests.py`, `tests_bug_fixes.py`, `tests_comments.py`
- Modify: `templates/pages/about.html`, `templates/pages/reservation.html`, `templates/reservation/edit-reservation.html`, `templates/reservation/delete-reservation.html`, `templates/pages/my_profile.html`, `templates/pages/massages_page.html` (if it references masseurs)
- Modify: `staticfiles/css/pages/my_profile.css` (`.masseur-*` classes)
- Create: `massageProject/main_app/migrations/0021_*.py` (generated)

**Interfaces:**
- Consumes: Task 2 state (model `Service`, param `service_id`).
- Produces: model `Specialist` (was `Masseur`); fields `WorkingHours.specialist`, `MessageReservation.specialist`; `check_availability` GET param `specialist_id`; context vars `specialists`, `specialist`; profile-context dict key `'specialist'` (was `'masseur'`); CSS classes `.specialist-*`; admin class `SpecialistAdmin`.

- [ ] **Step 1: Apply the renames to Python files (except populate_db)**

```bash
sed -i -E '
  s/MasseurAdmin/SpecialistAdmin/g;
  s/MasseurTranslationOptions/SpecialistTranslationOptions/g;
  s/main_app_masseur_changelist/main_app_specialist_changelist/g;
  s/masseur_id/specialist_id/g;
  s/\bMasseur\b/Specialist/g;
  s/\bmasseurs\b/specialists/g;
  s/\bmasseur\b/specialist/g;
' massageProject/main_app/models.py \
  massageProject/main_app/translation.py \
  massageProject/main_app/forms.py \
  massageProject/main_app/views.py \
  massageProject/main_app/admin.py \
  massageProject/settings.py \
  massageProject/main_app/tests.py \
  massageProject/main_app/tests_bug_fixes.py \
  massageProject/main_app/tests_comments.py
```

Cyrillic wording (`"Терапевт"`, `"%(name)s не работи в този ден."`) is unaffected by these ASCII patterns — verify via `git diff` that no Bulgarian text changed.

- [ ] **Step 2: Change the upload path**

In `massageProject/main_app/models.py`: `upload_to='masseurs/'` → `upload_to='specialists/'`.

- [ ] **Step 3: Manually edit populate_db.py**

Identifiers only; keep sample-data wording. Rename: import `Masseur` → `Specialist`, `masseurs_data` → `specialists_data`, `masseurs` → `specialists`, loop var `masseur` → `specialist`, `Masseur.objects.get_or_create` → `Specialist.objects.get_or_create`, `masseur=masseur` kwargs → `specialist=specialist`, and the image path string `'masseurs/measure.jpg'` → `'specialists/measure.jpg'`. The description string `'Expert in various massage techniques...'` stays verbatim.

Run: `grep -nE '\bMasseur\b|\bmasseur\b' massageProject/main_app/management/commands/populate_db.py`
Expected: no output.

- [ ] **Step 4: Apply the renames to templates and CSS**

```bash
sed -i -E '
  s/masseur_id/specialist_id/g;
  s/masseurId/specialistId/g;
  s/id_masseur/id_specialist/g;
  s/masseur-/specialist-/g;
  s/\bMasseur\b/Specialist/g;
  s/\bmasseurs\b/specialists/g;
  s/\bmasseur\b/specialist/g;
' templates/pages/about.html \
  templates/pages/reservation.html \
  templates/reservation/edit-reservation.html \
  templates/reservation/delete-reservation.html \
  templates/pages/my_profile.html \
  templates/pages/massages_page.html \
  staticfiles/css/pages/my_profile.css
```

Review `git diff`: the `alt="Masseur's Photo"` in about.html becomes `alt="Specialist's Photo"` (allowed — English-only, operator-invisible); `{% trans "Масажист" %}` labels stay; every `.masseur-*` class in the CSS has a matching `.specialist-*` usage in `my_profile.html` (`grep -o 'specialist-[a-z-]*' staticfiles/css/pages/my_profile.css | sort -u` vs the same grep on the template).

- [ ] **Step 5: Generate and inspect the migration**

Run: `python manage.py makemigrations main_app` — answer `y` to all rename prompts.
Inspect `0021_*.py`: only `RenameModel(old_name='Masseur', new_name='Specialist')`, `RenameField` for `workinghours.masseur`→`specialist` and `messagereservation.masseur`→`specialist`, plus `AlterField`s. Then `python manage.py migrate` → OK.

- [ ] **Step 6: Media dir + re-seed + full suite**

```bash
[ -d media/masseurs ] && mv media/masseurs media/specialists
python manage.py flush --noinput && python manage.py migrate && python manage.py populate_db
python manage.py test 2>&1 | tail -3
```
Expected: populate OK; `Ran N tests ... OK` with baseline N.

- [ ] **Step 7: Residual grep**

Run: `grep -rniE 'masseur' massageProject/ templates/ staticfiles/ --include='*.py' --include='*.html' --include='*.css' --include='*.js' | grep -v __pycache__ | grep -v 'migrations/00'`
Expected: no output (old migrations 0001–0019 keep historical names — that is correct and excluded).

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor: rename Masseur to Specialist across models, views, templates, CSS"
```

---

### Task 4: Rename the remaining model classes (Reservation, BusinessInfo, BusinessWorkingHours)

**Files:**
- Modify: `massageProject/main_app/models.py` (three class renames + `upload_to='studios/'`)
- Modify: `massageProject/main_app/translation.py`, `forms.py`, `views.py`, `admin.py`, `context_processors.py`
- Modify: `massageProject/accounts/views.py` (imports `MessageStudio`)
- Modify: `massageProject/settings.py` (sidebar links `main_app_messagestudio_changelist`, `main_app_messagereservation_changelist`)
- Modify: `massageProject/main_app/management/commands/populate_db.py`
- Modify: `massageProject/main_app/tests.py`, `tests_bug_fixes.py`, `tests_comments.py`
- Modify: `templates/pages/about.html`, `templates/pages/my_profile.html`, `templates/partials/footer.html`, `templates/pages/home.html`, `templates/partials/working_hours.html` (context var `studio` → `business_info`)
- Create: `massageProject/main_app/migrations/0022_*.py` (generated)

**Interfaces:**
- Consumes: Task 3 state.
- Produces: models `Reservation` (was `MessageReservation`), `BusinessInfo` (was `MessageStudio`), `BusinessWorkingHours` (was `StudioWorkingHours`); the `Comment.reservation` FK string reference `'Reservation'`; related accessor `homepage.business_working_hours` (was `studio_working_hours`); template context key `business_info` (was `studio`) from `context_processors.admin_branding`; email context key `business_info` (was `studio`) in `accounts.views` password-reset `extra_email_context`.

- [ ] **Step 1: Find every reference first**

Run: `grep -rln "MessageReservation\|MessageStudio\|StudioWorkingHours" massageProject/ templates/ --include='*.py' --include='*.html' | grep -v __pycache__ | grep -v migrations`
Expected file list matches the **Files** section above; if extra files appear, include them in Step 2.

- [ ] **Step 2: Apply the class renames**

```bash
sed -i -E '
  s/main_app_messagereservation_changelist/main_app_reservation_changelist/g;
  s/main_app_messagestudio_changelist/main_app_businessinfo_changelist/g;
  s/MessageReservation/Reservation/g;
  s/MessageStudio/BusinessInfo/g;
  s/StudioWorkingHours/BusinessWorkingHours/g;
  s/studio_working_hours/business_working_hours/g;
' $(grep -rln "MessageReservation\|MessageStudio\|StudioWorkingHours\|studio_working_hours\|main_app_messagestudio\|main_app_messagereservation" massageProject/ templates/ --include='*.py' --include='*.html' | grep -v __pycache__ | grep -v migrations)
```

The `studio_working_hours` rule renames the `related_name` on the `BusinessWorkingHours` FK to `HomePage` (in `models.py`) together with its two consumers: `homepage.studio_working_hours.order_by('order')` in `views.py` and `page.studio_working_hours.all` in `templates/partials/working_hours.html`. The related_name change appears in the migration as a no-op `AlterField` — that is expected.

This also fixes the string FK in `Comment`: `models.ForeignKey('MessageReservation', ...)` → `'Reservation'`. Verify: `grep -n "'Reservation'" massageProject/main_app/models.py` shows the Comment FK.

Collision check: `models.py` already defines nested `ReservationQuerySet`/`ReservationManager` — the sed does not touch them (different tokens). Confirm no duplicate `class Reservation` definitions: `grep -c "^class Reservation(" massageProject/main_app/models.py` → `1`.

- [ ] **Step 3: Rename the studio context var and upload path**

In `massageProject/main_app/context_processors.py`, rename the local var and context key:

```python
    try:
        business_info = BusinessInfo.objects.first()
    except Exception:
        business_info = None

    return {
        'brand_name': brand_name,
        'brand_logo': brand_logo,
        'footer_tagline': footer_tagline,
        'business_info': business_info,
    }
```

Then in the templates using it:

```bash
sed -i -E 's/\bstudio\b/business_info/g' templates/pages/about.html templates/pages/my_profile.html templates/partials/footer.html templates/pages/home.html templates/partials/working_hours.html
```

Review the diff: only `{{ studio.xxx }}` / `{% if studio.xxx %}` became `business_info.xxx`; Cyrillic wording and CSS classes like `footer-col--address` untouched.

In `massageProject/accounts/views.py`, the password-reset view's `extra_email_context` property (around line 33) builds a dict with a `'studio'` key — rename the local var and the key:

```python
        business_info = BusinessInfo.objects.first()
        ...
        return {
            'brand_name': homepage.brand_name if homepage else _('Relax & Health'),
            'business_info': business_info,
            'logo_url': logo_url,
        }
```

(Verified: no template under `templates/emails/` references `{{ studio`, so this key rename cannot break an email template — confirm with `grep -rn "studio" templates/emails/` → no output.)

In `models.py`: `upload_to='studios/'` → `upload_to='business/'`.

- [ ] **Step 4: Migration**

Run: `python manage.py makemigrations main_app` — answer `y` to the three rename prompts.
Inspect `0022_*.py`: only `RenameModel` ×3 + `AlterField` (upload_to). Then `python manage.py migrate` → OK.

- [ ] **Step 5: Media dir + re-seed + full suite**

```bash
[ -d media/studios ] && mv media/studios media/business
python manage.py flush --noinput && python manage.py migrate && python manage.py populate_db
python manage.py test 2>&1 | tail -3
```
Expected: `Ran N tests ... OK`.

- [ ] **Step 6: Residual grep + commit**

Run: `grep -rn "MessageReservation\|MessageStudio\|StudioWorkingHours\|studio_working_hours\|\bstudio\b" massageProject/ templates/ --include='*.py' --include='*.html' | grep -v __pycache__ | grep -v migrations`
Expected: no identifier hits (Cyrillic `"Студио"` verbose_name wording is allowed and expected to remain).

```bash
git add -A
git commit -m "refactor: rename MessageReservation, MessageStudio, StudioWorkingHours to neutral names"
```

---

### Task 5: Rename public URLs, URL names, and template files

**Files:**
- Modify: `massageProject/main_app/urls.py`
- Modify: `massageProject/main_app/views.py` (two `template_name` values)
- Rename: `templates/pages/massages_page.html` → `templates/pages/services_page.html`
- Rename: `templates/pages/massage_detail.html` → `templates/pages/service_detail.html`
- Modify: every template referencing `{% url 'massage_detail' %}` / `{% url 'massages_dashboard' %}` (header, home, partials, my_profile, massages_page content)
- Modify: `massageProject/main_app/tests.py`, `tests_bug_fixes.py` (any `reverse('massage_detail')` / `reverse('massages_dashboard')` / hardcoded `/massages/` paths)

**Interfaces:**
- Consumes: view classes `ServicesDashboard`, `ServiceDetail` (Task 2).
- Produces: URL paths `/services/`, `/service/<int:pk>/`; URL names `services_dashboard`, `service_detail`; templates `pages/services_page.html`, `pages/service_detail.html`. All other URL names (`reservation_page`, `check_availability`, etc.) unchanged.

- [ ] **Step 1: Rename the template files**

```bash
git mv templates/pages/massages_page.html templates/pages/services_page.html
git mv templates/pages/massage_detail.html templates/pages/service_detail.html
```

- [ ] **Step 2: Update urls.py**

In `massageProject/main_app/urls.py` change the two routes:

```python
    path('services/', ServicesDashboard.as_view(), name='services_dashboard'),
    ...
    path('service/<int:pk>/', ServiceDetail.as_view(), name='service_detail'),
```

(replacing `path('massages/', ...)` / `name='massages_dashboard'` and `path('massage/<int:pk>/', ...)` / `name='massage_detail'`).

- [ ] **Step 3: Update template_name and all references**

```bash
sed -i "s|pages/massages_page.html|pages/services_page.html|; s|pages/massage_detail.html|pages/service_detail.html|" massageProject/main_app/views.py
grep -rln "massages_dashboard\|massage_detail\|massages_page\|massage_detail" templates/ massageProject/ --include='*.py' --include='*.html' | grep -v __pycache__ | grep -v migrations | xargs sed -i -E '
  s/massages_dashboard/services_dashboard/g;
  s/massage_detail/service_detail/g;
  s/massages_page/services_page/g;
'
```

- [ ] **Step 4: Update hardcoded test paths**

Run: `grep -rn "'/massages/\|'/massage/" massageProject/ --include='*.py' | grep -v __pycache__`
For each hit, change `/massages/` → `/services/` and `/massage/<pk>/` style paths → `/service/<pk>/`.

- [ ] **Step 5: Full suite + link check**

```bash
python manage.py test 2>&1 | tail -3
grep -rn "massages_dashboard\|massage_detail" templates/ massageProject/ --include='*.py' --include='*.html' | grep -v __pycache__ | grep -v migrations
```
Expected: `Ran N tests ... OK`; second command prints nothing.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: rename massage URLs, URL names, and page templates to service equivalents"
```

---

### Task 6: Final sweep, base title fix, i18n check, smoke test

**Files:**
- Modify: `templates/base.html` (title)
- Possibly modify: `locale/bg/LC_MESSAGES/django.po`, `locale/en/LC_MESSAGES/django.po` (location-comment churn only)

**Interfaces:**
- Consumes: Tasks 2–5 complete.
- Produces: Part 1 done — repo-wide identifier neutrality, suite green, site smoke-tested.

- [ ] **Step 1: Fix the hardcoded title (the one intentional visible change)**

In `templates/base.html` change:

```html
    <title>Massage Center</title>
```
to:
```html
    <title>{{ brand_name }}</title>
```

`brand_name` is already supplied on every page by `main_app.context_processors.admin_branding`. The title now shows the configured brand ("Relax & Health" from `HomePage.get_solo` defaults).

- [ ] **Step 2: Repo-wide final sweep**

```bash
grep -rniE 'massage|masseur|messagereservation|messagestudio|studioworkinghours' \
  massageProject/ templates/ staticfiles/ \
  --include='*.py' --include='*.html' --include='*.css' --include='*.js' \
  | grep -v __pycache__ | grep -v 'migrations/00' | grep -vi 'massageProject'
```

Every remaining hit must be on the allowed list:
1. Bulgarian wording: `Масаж`, `масаж`, `Масажист`, `Терапевт` inside `verbose_name`s, `{% trans %}` strings, validation messages (unchanged by design; Part 2 replaces them with the terminology system).
2. `populate_db` sample-data strings (`'Swedish Massage'`, `'...massage techniques...'`).
3. `admin.site.site_header = "Massage Studio Administration"` in `massageProject/urls.py` (deferred to Part 2).

Anything else — a missed identifier — fix it now and rerun the sweep.

- [ ] **Step 3: i18n check (no new msgids expected)**

```bash
python manage.py makemessages -l bg -l en
git diff --stat locale/
```
Expected: only `#: path:line` location-comment and timestamp churn — no new `msgid` entries (Part 1 introduces no new static text). If a new msgid appears, a wording string was accidentally changed — trace it and revert the wording. Then:

```bash
python manage.py compilemessages
```

- [ ] **Step 4: Full suite one last time**

Run: `python manage.py test 2>&1 | tail -3`
Expected: `Ran N tests ... OK` (baseline N from Task 1).

- [ ] **Step 5: Manual smoke test**

```bash
python manage.py runserver
```
Visit and confirm identical rendering to pre-refactor (except the tab title now shows the brand name): `/` (home, featured services, carousel), `/services/` (dashboard incl. group filter), `/service/1/` (detail), `/reserve/` (form loads; picking a service+specialist+date fetches slots — proves the `service_id`/`specialist_id` JS↔view contract), `/about/`, `/profile/` (reservations table incl. `.specialist-*` styled cells), `/gallery/`, footer contact block (`business_info` fields). Log into `/admin/` and confirm the Unfold sidebar links (Услуги, Терапевти, Резервации, Студио section) all resolve.

- [ ] **Step 6: Commit and merge readiness**

```bash
git add -A
git commit -m "refactor: brand-neutral title, i18n regen, final neutralization sweep"
```

Then use superpowers:finishing-a-development-branch to decide merge/PR for `white-label-part1`.

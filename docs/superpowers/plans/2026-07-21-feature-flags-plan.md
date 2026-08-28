# Feature Flag Enforcement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `SiteConfiguration`'s three feature flags (`booking_enabled`,
`comments_enabled`, `google_login_enabled`, from Plan A) actually control the
site: hide the relevant UI when a flag is off, and independently enforce it
server-side so direct URL access or a raw POST can't bypass the UI hiding.

**Architecture:** Two-layer enforcement per flag, per the approved design
doc's own table (`docs/superpowers/specs/2026-07-19-white-label-platform-
design.md`, section 2d). A small mixin + matching function-view decorator in
`massageProject/main_app/mixins.py` raise `Http404` when a flag is off,
applied to the relevant views; templates read `site_config.<flag>` (already
in every template's context via Plan A) to hide the corresponding UI.
`google_login_enabled` additionally guards `allauth`'s social adapter so
direct OAuth callback access can't bypass a hidden button.

**Tech Stack:** Django class-based/function views, template `{% if %}`
guards — no new models (the 3 boolean fields already exist on
`SiteConfiguration` from Plan A).

## Global Constraints

- This is Plan D (final plan) of the 4-plan split of Part 2 ("Brand
  Configuration"), building on Plan A (`SiteConfiguration` model), Plan B
  (theme mechanics), and Plan C (terminology), all already merged.
- All three flags default to `True` (Plan A) — the existing massage-demo
  instance must render and behave **exactly as it does today** with no
  admin changes required.
- A flag being off must produce a real `404` (via `Http404`), not a silent
  empty page or a 500 — every server-side test must assert
  `status_code == 404`.
- Do not touch `massageProject/main_app/models.py` or any migration — the
  3 flag fields already exist; this plan only consumes them.
- Do not touch `massageProject/main_app/theme.py`, `theme_extras.py`, or any
  hero partial's layout/CSS beyond wrapping the existing CTA link in an
  `{% if %}` — no visual redesign in this plan.
- Per CLAUDE.md, this plan's final task must regenerate translation
  catalogs for any brand-new static text (there should be very few — most
  changes are `{% if %}` wrapping existing already-translated strings; the
  one new string is the auth modal's generalized subtitle).

---

### Task 1: `booking_enabled` — server-side enforcement

**Files:**
- Modify: `massageProject/main_app/mixins.py`
- Modify: `massageProject/main_app/views.py`
- Test: `massageProject/main_app/tests_feature_flags.py` (new file)

**Interfaces:**
- Produces: `BookingEnabledMixin` (class-based view mixin) and
  `booking_enabled_required` (function-view decorator) in
  `massageProject/main_app/mixins.py`, both raising `django.http.Http404`
  when `SiteConfiguration.get_solo().booking_enabled` is `False`. Task 2
  (UI hiding) and Task 3 (comments, for the analogous pattern) consume this
  file; Task 5's regression run exercises all of it together.

- [ ] **Step 1: Write the failing tests**

Create `massageProject/main_app/tests_feature_flags.py`:

```python
from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

from massageProject.main_app.models import Service, Specialist, WorkingHours, Reservation, SiteConfiguration

User = get_user_model()


class BookingEnabledServerEnforcementTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone_number='0888777001', email='bookingflag@example.com',
            password='testpass123', first_name='Test', last_name='User',
        )
        self.specialist = Specialist.objects.create(
            name='Flag Test Specialist', description='desc', phone_number='0888777001',
            email='flagspecialist@example.com',
        )
        self.service = Service.objects.create(
            name='Flag Test Service', description='desc', price=50, duration_in_minutes=60,
            short_description='short',
        )
        WorkingHours.objects.create(
            specialist=self.specialist, day_of_week=(date.today() + timedelta(days=3)).weekday(),
            start_time=time(9, 0), end_time=time(18, 0),
        )
        self.reservation = Reservation.objects.create(
            service=self.service, specialist=self.specialist, user=self.user,
            date=date.today() + timedelta(days=3), time=time(10, 0),
        )
        self.client.force_login(self.user)

    def _disable_booking(self):
        config = SiteConfiguration.get_solo()
        config.booking_enabled = False
        config.save()

    def test_reservation_page_404s_when_booking_disabled(self):
        self._disable_booking()
        response = self.client.get('/bg/reserve/')
        self.assertEqual(response.status_code, 404)

    def test_reservation_page_200s_when_booking_enabled(self):
        response = self.client.get('/bg/reserve/')
        self.assertEqual(response.status_code, 200)

    def test_edit_reservation_404s_when_booking_disabled(self):
        self._disable_booking()
        response = self.client.get(f'/{self.reservation.pk}/edit_reserve/')
        self.assertEqual(response.status_code, 404)

    def test_delete_reservation_404s_when_booking_disabled(self):
        self._disable_booking()
        response = self.client.get(f'/{self.reservation.pk}/delete_reserve/')
        self.assertEqual(response.status_code, 404)

    def test_check_availability_404s_when_booking_disabled(self):
        self._disable_booking()
        response = self.client.get(
            f'/bg/check-availability/?specialist_id={self.specialist.pk}'
            f'&service_id={self.service.pk}&date=2030-01-01'
        )
        self.assertEqual(response.status_code, 404)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test massageProject.main_app.tests_feature_flags -v 2`
Expected: `test_reservation_page_200s_when_booking_enabled` PASSES (nothing
changed yet), all 4 disabled-flag tests FAIL with `404 != 200` (the views
don't check the flag yet).

- [ ] **Step 3: Add the mixin and decorator**

Append to `massageProject/main_app/mixins.py`:

```python
from functools import wraps

from django.http import Http404


class BookingEnabledMixin:
    def dispatch(self, request, *args, **kwargs):
        from massageProject.main_app.models import SiteConfiguration
        if not SiteConfiguration.get_solo().booking_enabled:
            raise Http404
        return super().dispatch(request, *args, **kwargs)


def booking_enabled_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from massageProject.main_app.models import SiteConfiguration
        if not SiteConfiguration.get_solo().booking_enabled:
            raise Http404
        return view_func(request, *args, **kwargs)
    return wrapper
```

(The `SiteConfiguration` import stays local to each function/method to avoid
a circular import — `models.py` does not import `mixins.py`, but keeping the
import local here matches the fact that `mixins.py` currently has zero
model imports and avoids introducing one at module level for a file whose
only other class, `DisableFieldMixin`, is pure `forms.Form` logic.)

- [ ] **Step 4: Apply them to the 4 booking views**

In `massageProject/main_app/views.py`:

1. Add `from massageProject.main_app.mixins import BookingEnabledMixin, booking_enabled_required` to the existing import block for `massageProject.main_app.mixins` (currently `from massageProject.main_app.forms import ...` is the only mixins-adjacent import — add this as a new import line).

2. Change the `ReservationPage` class declaration from:
```python
class ReservationPage(LoginRequiredMixin, CreateView):
```
to:
```python
class ReservationPage(BookingEnabledMixin, LoginRequiredMixin, CreateView):
```

3. Change `edit_reservation` from:
```python
@login_required
def edit_reservation(request, pk: int):
```
to:
```python
@booking_enabled_required
@login_required
def edit_reservation(request, pk: int):
```

4. Change `delete_reservation` from:
```python
@login_required
def delete_reservation(request, pk: int):
```
to:
```python
@booking_enabled_required
@login_required
def delete_reservation(request, pk: int):
```

5. Change `check_availability` from:
```python
@login_required
def check_availability(request):
```
to:
```python
@booking_enabled_required
@login_required
def check_availability(request):
```

Putting `booking_enabled_required` as the outermost decorator (and
`BookingEnabledMixin` leftmost in `ReservationPage`'s bases) means the flag
check runs *before* the login check in every case — a disabled flag always
produces 404 regardless of authentication state, matching the brief's
"returns 404" requirement without an auth-dependent redirect getting in the
way first.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python manage.py test massageProject.main_app.tests_feature_flags -v 2`
Expected: PASS — all 5 tests green.

- [ ] **Step 6: Run the full test suite**

Run: `python manage.py test -v 2`
Expected: PASS — no regressions (163 pre-existing + 5 new).

- [ ] **Step 7: Commit**

```bash
git add massageProject/main_app/mixins.py massageProject/main_app/views.py \
        massageProject/main_app/tests_feature_flags.py
git commit -m "feat: enforce booking_enabled flag server-side on all booking views"
```

---

### Task 2: `booking_enabled` — UI hiding

**Files:**
- Modify: `templates/partials/header.html`
- Modify: `templates/partials/hero/split.html`
- Modify: `templates/partials/hero/carousel.html`
- Modify: `templates/partials/hero/fullbleed.html`
- Modify: `templates/pages/service_detail.html`
- Modify: `templates/pages/my_profile.html`
- Modify: `templates/partials/auth_modal.html`
- Test: `massageProject/main_app/tests_feature_flags.py` (append)

**Interfaces:**
- Consumes: `site_config.booking_enabled` (Plan A, already in every
  template's context).

- [ ] **Step 1: Write the failing tests**

Append to `massageProject/main_app/tests_feature_flags.py`:

```python
class BookingEnabledUIHidingTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone_number='0888777002', email='bookingui@example.com',
            password='testpass123', first_name='Test', last_name='User',
        )
        self.specialist = Specialist.objects.create(
            name='UI Test Specialist', description='desc', phone_number='0888777002',
            email='uispecialist@example.com',
        )
        self.service = Service.objects.create(
            name='UI Test Service', description='desc', price=50, duration_in_minutes=60,
            short_description='short', image='specialists/measure.jpg',
        )
        WorkingHours.objects.create(
            specialist=self.specialist, day_of_week=(date.today() + timedelta(days=3)).weekday(),
            start_time=time(9, 0), end_time=time(18, 0),
        )
        self.reservation = Reservation.objects.create(
            service=self.service, specialist=self.specialist, user=self.user,
            date=date.today() + timedelta(days=3), time=time(10, 0),
        )
        self.client.force_login(self.user)

    def _disable_booking(self):
        config = SiteConfiguration.get_solo()
        config.booking_enabled = False
        config.save()

    def test_navbar_cta_hidden_when_booking_disabled(self):
        self._disable_booking()
        response = self.client.get('/bg/')
        content = response.content.decode()
        self.assertNotIn('navbar-cta', content)

    def test_hero_reservation_cta_hidden_when_booking_disabled(self):
        self._disable_booking()
        response = self.client.get('/bg/')
        content = response.content.decode()
        self.assertNotIn("{% url 'reservation_page' %}", content)  # sanity: raw tag never leaks
        self.assertNotIn('/reserve/', content)

    def test_service_detail_booking_button_hidden_when_disabled(self):
        self._disable_booking()
        response = self.client.get(f'/bg/service/{self.service.pk}/')
        content = response.content.decode()
        self.assertNotIn('Направи резервация', content)

    def test_profile_reservation_actions_hidden_when_disabled(self):
        self._disable_booking()
        response = self.client.get('/bg/profile/')
        content = response.content.decode()
        self.assertNotIn('Запазете нов час', content)
        self.assertNotIn('Промени', content)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test massageProject.main_app.tests_feature_flags.BookingEnabledUIHidingTest -v 2`
Expected: FAIL on all 4 — nothing is hidden yet.

- [ ] **Step 3: Hide the navbar CTA**

In `templates/partials/header.html`, wrap the existing CTA:

```html
        <a href="{% url 'reservation_page' %}" class="btn btn-primary navbar-cta" data-auth-modal-link title="{% trans 'Запазете час' %}">
            <i class="fas fa-calendar-alt"></i>
            <span>{% trans "Запазете час" %}</span>
        </a>
```

with:

```html
        {% if site_config.booking_enabled %}
        <a href="{% url 'reservation_page' %}" class="btn btn-primary navbar-cta" data-auth-modal-link title="{% trans 'Запазете час' %}">
            <i class="fas fa-calendar-alt"></i>
            <span>{% trans "Запазете час" %}</span>
        </a>
        {% endif %}
```

- [ ] **Step 4: Hide each hero variant's reservation CTA**

In `templates/partials/hero/split.html`, wrap:
```html
                <a href="{% url 'reservation_page' %}" class="btn btn-primary btn-lg" data-auth-modal-link>{% trans "Запазете час" %}</a>
```
with `{% if site_config.booking_enabled %}` / `{% endif %}` (leave the
adjacent "Вижте услугите" link outside the `{% if %}`, untouched).

In `templates/partials/hero/carousel.html`, wrap the identical line the same
way (also leave "Вижте услугите" untouched).

In `templates/partials/hero/fullbleed.html`, wrap:
```html
        <a href="{% url 'reservation_page' %}" class="btn btn-primary btn-lg" data-auth-modal-link>{% trans "Запазете час" %}</a>
```
with `{% if site_config.booking_enabled %}` / `{% endif %}` (this is the
only CTA in that variant).

- [ ] **Step 5: Make the service detail page info-only when booking is disabled**

In `templates/pages/service_detail.html`, wrap:
```html
        <a href="{% url 'reservation_page' pk=service.pk %}" class="btn" data-auth-modal-link>{% trans "Направи резервация" %}</a>
```
with `{% if site_config.booking_enabled %}` / `{% endif %}`.

- [ ] **Step 6: Hide the profile page's reservation actions**

In `templates/pages/my_profile.html`, wrap the "book a new appointment" CTA:
```html
          <a href="{% url 'reservation_page' %}" class="btn-primary-profile" data-auth-modal-link>+ {% trans "Запазете нов час" %}</a>
```
with `{% if site_config.booking_enabled %}` / `{% endif %}`.

Also wrap the per-row edit/cancel action links inside the upcoming-
reservations table:
```html
                <a href="{% url 'edit_reservation' r.id %}" class="btn-action-edit">{% trans "Промени" %}</a>
                <a href="{% url 'delete_reservation' r.id %}" class="btn-action-cancel">&times; {% trans "Отмени" %}</a>
```
with a single `{% if site_config.booking_enabled %}` / `{% endif %}` around
both lines together (the calendar-add button, `disabled` already, stays as
it is — it does nothing regardless of the flag).

- [ ] **Step 7: Generalize the auth modal subtitle**

The auth modal is triggered by both booking and leaving a review, so its
subtitle shouldn't assume booking is the reason. In
`templates/partials/auth_modal.html`, change:

```html
      <p class="auth-modal-subtitle">{% trans "За да завършите резервацията, трябва да потвърдим Вашия имейл." %}</p>
```

to:

```html
      <p class="auth-modal-subtitle">{% trans "Трябва да потвърдим Вашия имейл, за да продължите." %}</p>
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `python manage.py test massageProject.main_app.tests_feature_flags -v 2`
Expected: PASS — all tests green.

- [ ] **Step 9: Run the full test suite**

Run: `python manage.py test -v 2`
Expected: PASS — no regressions. (The `test_hero_reservation_cta_hidden_when_booking_disabled`
test's first assertion, checking the raw `{% url %}` tag never leaks, will
trivially pass regardless — Django never renders unparsed template tags into
output — but is kept as a documentation-of-intent assertion; the real check
is the second assertion.)

- [ ] **Step 10: Commit**

```bash
git add templates/partials/header.html templates/partials/hero/split.html \
        templates/partials/hero/carousel.html templates/partials/hero/fullbleed.html \
        templates/pages/service_detail.html templates/pages/my_profile.html \
        templates/partials/auth_modal.html massageProject/main_app/tests_feature_flags.py
git commit -m "feat: hide booking CTAs across the site when booking_enabled is off"
```

---

### Task 3: `comments_enabled` — server enforcement + UI hiding

**Files:**
- Modify: `massageProject/main_app/mixins.py`
- Modify: `massageProject/main_app/views.py`
- Modify: `templates/pages/home.html`
- Modify: `templates/pages/about.html`
- Test: `massageProject/main_app/tests_feature_flags.py` (append)

**Interfaces:**
- Consumes: `BookingEnabledMixin`'s sibling pattern from Task 1 (mirrored,
  not reused — a separate flag needs a separate mixin/decorator).
- Produces: `CommentsEnabledMixin`, `comments_enabled_required` in
  `massageProject/main_app/mixins.py`.

- [ ] **Step 1: Write the failing tests**

Append to `massageProject/main_app/tests_feature_flags.py`:

```python
class CommentsEnabledServerEnforcementTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone_number='0888777003', email='commentsflag@example.com',
            password='testpass123', first_name='Test', last_name='User',
        )
        self.client.force_login(self.user)

    def _disable_comments(self):
        config = SiteConfiguration.get_solo()
        config.comments_enabled = False
        config.save()

    def test_all_comments_view_404s_when_disabled(self):
        self._disable_comments()
        response = self.client.get('/bg/comments/')
        self.assertEqual(response.status_code, 404)

    def test_all_comments_view_200s_when_enabled(self):
        response = self.client.get('/bg/comments/')
        self.assertEqual(response.status_code, 200)

    def test_submit_comment_404s_when_disabled(self):
        self._disable_comments()
        response = self.client.post('/bg/submit-comment/', {'content': 'test', 'rating': 5})
        self.assertEqual(response.status_code, 404)

    def test_about_page_post_404s_when_comments_disabled(self):
        self._disable_comments()
        response = self.client.post('/bg/about/', {'content': 'test comment'})
        self.assertEqual(response.status_code, 404)

    def test_about_page_get_still_200s_when_comments_disabled(self):
        self._disable_comments()
        response = self.client.get('/bg/about/')
        self.assertEqual(response.status_code, 200)


class CommentsEnabledUIHidingTest(TestCase):
    def _disable_comments(self):
        config = SiteConfiguration.get_solo()
        config.comments_enabled = False
        config.save()

    def test_home_reviews_section_hidden_when_disabled(self):
        self._disable_comments()
        response = self.client.get('/bg/')
        content = response.content.decode()
        self.assertNotIn('hp-reviews', content)

    def test_about_page_comments_section_hidden_when_disabled(self):
        self._disable_comments()
        response = self.client.get('/bg/about/')
        content = response.content.decode()
        self.assertNotIn('class="comments"', content)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test massageProject.main_app.tests_feature_flags.CommentsEnabledServerEnforcementTest massageProject.main_app.tests_feature_flags.CommentsEnabledUIHidingTest -v 2`
Expected: FAIL on every disabled-flag test (the enabled-flag ones already
pass, nothing changed for them yet).

- [ ] **Step 3: Add the comments mixin and decorator**

Append to `massageProject/main_app/mixins.py`:

```python
class CommentsEnabledMixin:
    def dispatch(self, request, *args, **kwargs):
        from massageProject.main_app.models import SiteConfiguration
        if not SiteConfiguration.get_solo().comments_enabled:
            raise Http404
        return super().dispatch(request, *args, **kwargs)


def comments_enabled_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from massageProject.main_app.models import SiteConfiguration
        if not SiteConfiguration.get_solo().comments_enabled:
            raise Http404
        return view_func(request, *args, **kwargs)
    return wrapper
```

- [ ] **Step 4: Apply them in views.py**

In `massageProject/main_app/views.py`:

1. Add `CommentsEnabledMixin, comments_enabled_required` to the
   `massageProject.main_app.mixins` import line (now importing
   `BookingEnabledMixin, booking_enabled_required, CommentsEnabledMixin,
   comments_enabled_required`).

2. Change `AllCommentsView`'s class declaration from:
```python
class AllCommentsView(ListView):
```
to:
```python
class AllCommentsView(CommentsEnabledMixin, ListView):
```

3. Change `submit_comment` from:
```python
@login_required
@require_POST
def submit_comment(request):
```
to:
```python
@comments_enabled_required
@login_required
@require_POST
def submit_comment(request):
```

4. In `AboutPage.post()` (the method that handles the comment-submission
   form on the about page), add a guard as the very first line of the
   method body:
```python
    def post(self, request, *args, **kwargs):
        from massageProject.main_app.models import SiteConfiguration
        if not SiteConfiguration.get_solo().comments_enabled:
            raise Http404
        user = request.user
        ...
```
   (keep the rest of the existing method body unchanged below the new
   guard — this only blocks the POST/comment-creation path; `AboutPage.get()`
   via `get_context_data` is untouched, so the bio content still renders).
   Add `from django.http import Http404` to the existing import block at
   the top of `views.py` if it is not already imported (it currently is
   not — `views.py` imports `get_object_or_404` but not `Http404`).

- [ ] **Step 5: Hide the reviews section on the home page**

In `templates/pages/home.html`, wrap the entire `<!-- ========== REVIEWS —
Two-card carousel ========== -->` section (from `<section class="hp-reviews">`
through its closing `</section>`) and the adjacent `<!-- ========== REVIEW
MODAL ========== -->` block (the `<div class="hp-modal-overlay" ...>` through
its closing `</div>`) in a single `{% if site_config.comments_enabled %}` /
`{% endif %}` pair, so neither renders when comments are disabled.

- [ ] **Step 6: Hide the comments section on the about page**

In `templates/pages/about.html`, wrap the entire `<section class="comments">`
block (from `<section class="comments">` through its closing `</section>`)
in `{% if site_config.comments_enabled %}` / `{% endif %}`.

- [ ] **Step 7: Run tests to verify they pass**

Run: `python manage.py test massageProject.main_app.tests_feature_flags -v 2`
Expected: PASS — all tests green.

- [ ] **Step 8: Run the full test suite**

Run: `python manage.py test -v 2`
Expected: PASS — no regressions.

- [ ] **Step 9: Commit**

```bash
git add massageProject/main_app/mixins.py massageProject/main_app/views.py \
        templates/pages/home.html templates/pages/about.html \
        massageProject/main_app/tests_feature_flags.py
git commit -m "feat: enforce comments_enabled flag server-side and hide comment UI when off"
```

---

### Task 4: `google_login_enabled` — adapter guard + UI hiding

**Files:**
- Modify: `massageProject/accounts/adapters.py`
- Modify: `templates/partials/auth_modal.html`
- Test: `massageProject/accounts/tests_google_login_flag.py` (new file)

**Interfaces:**
- Consumes: `SiteConfiguration.get_solo().google_login_enabled` (Plan A).
- Produces: `GoogleSocialAccountAdapter.is_open_for_signup` now also
  returns `False` when the flag is off, refusing the social-login flow at
  the adapter layer (so a direct callback hit can't bypass a hidden
  button); the auth modal's Google button/form is conditionally hidden.

- [ ] **Step 1: Write the failing tests**

Create `massageProject/accounts/tests_google_login_flag.py`:

```python
from unittest.mock import MagicMock

from django.test import TestCase

from massageProject.accounts.adapters import GoogleSocialAccountAdapter
from massageProject.main_app.models import SiteConfiguration


class GoogleLoginFlagAdapterTest(TestCase):
    def test_is_open_for_signup_true_when_flag_enabled(self):
        adapter = GoogleSocialAccountAdapter()
        sociallogin = MagicMock()
        self.assertTrue(adapter.is_open_for_signup(request=None, sociallogin=sociallogin))

    def test_is_open_for_signup_false_when_flag_disabled(self):
        config = SiteConfiguration.get_solo()
        config.google_login_enabled = False
        config.save()
        adapter = GoogleSocialAccountAdapter()
        sociallogin = MagicMock()
        self.assertFalse(adapter.is_open_for_signup(request=None, sociallogin=sociallogin))


class GoogleLoginFlagUITest(TestCase):
    def test_google_button_hidden_when_flag_disabled(self):
        config = SiteConfiguration.get_solo()
        config.google_login_enabled = False
        config.save()
        response = self.client.get('/bg/')
        content = response.content.decode()
        self.assertNotIn('auth-modal-google-btn', content)

    def test_google_button_present_when_flag_enabled(self):
        response = self.client.get('/bg/')
        content = response.content.decode()
        self.assertIn('auth-modal-google-btn', content)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test massageProject.accounts.tests_google_login_flag -v 2`
Expected: FAIL on `test_is_open_for_signup_false_when_flag_disabled` (still
returns `True` unconditionally) and `test_google_button_hidden_when_flag_disabled`
(button always renders). The two "enabled" tests already pass.

- [ ] **Step 3: Guard the adapter**

In `massageProject/accounts/adapters.py`, change:

```python
class GoogleSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Auto-link a first-time Google login to an existing account with the
    same email. Existing users have no allauth EmailAddress records, so the
    built-in SOCIALACCOUNT_EMAIL_AUTHENTICATION matching would never find
    them; we match on CustomUser.email directly. Only provider-verified
    emails are trusted (Google always verifies)."""

    def is_open_for_signup(self, request, sociallogin):
        # The default delegates to the account adapter, which is closed;
        # social signup (the Google complete-profile step) must stay open.
        return True
```

to:

```python
class GoogleSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Auto-link a first-time Google login to an existing account with the
    same email. Existing users have no allauth EmailAddress records, so the
    built-in SOCIALACCOUNT_EMAIL_AUTHENTICATION matching would never find
    them; we match on CustomUser.email directly. Only provider-verified
    emails are trusted (Google always verifies)."""

    def is_open_for_signup(self, request, sociallogin):
        # The default delegates to the account adapter, which is closed;
        # social signup (the Google complete-profile step) must stay open,
        # unless the brand has turned Google login off entirely.
        from massageProject.main_app.models import SiteConfiguration
        return SiteConfiguration.get_solo().google_login_enabled
```

- [ ] **Step 4: Hide the Google button in the auth modal**

In `templates/partials/auth_modal.html`, wrap the entire Google form block:

```html
      <div class="auth-modal-divider"><span>{% trans "или" %}</span></div>
      <form method="post" action="{% url 'google_login' %}" class="auth-modal-google-form">
        {% csrf_token %}
        <input type="hidden" name="next" id="auth-google-next" value="">
        <button type="submit" class="auth-modal-google-btn">
          <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 0 1-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z"/><path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z"/><path fill="#FBBC05" d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332z"/><path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z"/></svg>
          {% trans "Продължи с Google" %}
        </button>
      </form>
```

with the same content wrapped in `{% if site_config.google_login_enabled %}`
/ `{% endif %}`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python manage.py test massageProject.accounts.tests_google_login_flag -v 2`
Expected: PASS — all 4 tests green.

- [ ] **Step 6: Run the full test suite**

Run: `python manage.py test -v 2`
Expected: PASS — no regressions, including the pre-existing
`massageProject.accounts.tests_google_oauth` tests (which exercise the
default enabled-flag path and must be unaffected).

- [ ] **Step 7: Commit**

```bash
git add massageProject/accounts/adapters.py templates/partials/auth_modal.html \
        massageProject/accounts/tests_google_login_flag.py
git commit -m "feat: enforce google_login_enabled flag at the adapter layer and hide the button"
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
Expected: PASS — every test in the project passes (Plans A/B/C's tests,
plus this plan's new `tests_feature_flags.py` and
`tests_google_login_flag.py`).

- [ ] **Step 2: Regenerate message catalogs**

```bash
source venv/bin/activate
python manage.py makemessages -l bg -l en
```

This plan introduces exactly one brand-new `msgid`: the auth modal's
generalized subtitle, `"Трябва да потвърдим Вашия имейл, за да продължите."`
(replacing `"За да завършите резервацията, трябва да потвърдим Вашия
имейл."`, which becomes an obsolete `#~` entry — expected). Every other
change in this plan is `{% if %}` wrapping around already-translated
strings, so no other new msgids should appear. Add to both
`locale/bg/LC_MESSAGES/django.po` and `locale/en/LC_MESSAGES/django.po`:

| msgid (bg, source) | bg msgstr | en msgstr |
|---|---|---|
| `Трябва да потвърдим Вашия имейл, за да продължите.` | (same, verbatim) | `We need to verify your email to continue.` |

If `makemessages` surfaces any *other* new empty `msgstr`, that means a
`{% trans %}` tag was added/changed somewhere beyond what this plan
describes — fill it in with an accurate bg/en translation before proceeding,
and note the discrepancy in your report.

- [ ] **Step 3: Compile messages**

```bash
python manage.py compilemessages
```

- [ ] **Step 4: Commit**

```bash
git add locale/bg/LC_MESSAGES/django.po locale/bg/LC_MESSAGES/django.mo \
        locale/en/LC_MESSAGES/django.po locale/en/LC_MESSAGES/django.mo
git commit -m "chore: regenerate translation catalogs after feature flag changes"
```

---

## Plan Self-Review Notes

- **Spec coverage:** matches the approved design doc's Part 2d table
  exactly — `booking_enabled` (✅ Tasks 1-2: `ReservationPage`,
  `edit_reservation`, `delete_reservation`, `check_availability` 404 via
  mixin/decorator; nav CTA, hero CTAs, service detail button, profile
  actions, auth-modal generic text), `comments_enabled` (✅ Task 3:
  `AllCommentsView`/`submit_comment` 404 via mixin/decorator, plus
  `AboutPage.post()` guarded defense-in-depth; home reviews section and
  about comments section hidden), `google_login_enabled` (✅ Task 4:
  `GoogleSocialAccountAdapter.is_open_for_signup` guard, Google button
  hidden). i18n regenerated (✅ Task 5).
- **Placeholder scan:** no TBD/TODO; every step has literal before/after
  code or exact new file contents.
- **Type consistency:** `site_config.booking_enabled`/`.comments_enabled`/
  `.google_login_enabled` are the exact field names Plan A defined on
  `SiteConfiguration` — verified consistent across all 4 tasks. Mixin/
  decorator naming (`BookingEnabledMixin`/`booking_enabled_required`,
  `CommentsEnabledMixin`/`comments_enabled_required`) is parallel and
  consistent between Task 1 and Task 3.

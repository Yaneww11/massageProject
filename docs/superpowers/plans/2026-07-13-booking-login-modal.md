# Email-First Booking Login/Signup Modal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the full-page login/register/email-verification flow with a single email-first modal (email → password-or-code branch for existing users, code→registration for new users) triggered from every "Book Now" link and the header Login/Register links, with rate limiting, a honeypot, and Cloudflare Turnstile protecting the sensitive endpoints.

**Architecture:** Five small JSON endpoints in a new `accounts/booking_auth_views.py` (`check-email`, `send-code`, `verify-code`, `login-password`, `register`) back a single vanilla-JS modal partial included in `base.html`. A new `EmailOTP` model stores hashed one-time codes. The old link-click email-verification flow, full-page login/register, and their views/forms/templates are removed; a lightweight `AuthEntryView` keeps the `login` URL name alive (still needed as Django's default `LOGIN_URL` for `ProfilePage`/`edit_reservation`/`delete_reservation`) by auto-opening the same modal.

**Tech Stack:** Django 6.0.6, `django-ratelimit` (new dependency), Cloudflare Turnstile (external service, new dependency: `requests` — already installed), vanilla JS/CSS (no framework, matches existing codebase).

## Global Constraints

- Rate limits: `send-code` 5/min per IP + 3/min per email; `verify-code` and `login-password` 10/min per IP + 8/min per email; `register` 5/min per IP. All via `django-ratelimit` with `block=False` + manual `request.limited` check (JSON 429 response), not the library's default exception-raising behavior.
- OTP codes: 6 digits, numeric, stored only as a hash (`django.contrib.auth.hashers.make_password`/`check_password`), 10-minute expiry, dead after 5 wrong attempts.
- Honeypot field name: `middle_name`, hidden off-screen via CSS (not `display:none`, to survive basic bot heuristics), present only on the registration step. Non-empty → fake success, nothing created.
- Cloudflare Turnstile: env vars `TURNSTILE_SITE_KEY` / `TURNSTILE_SECRET_KEY`, both default to `''`. **You must create a free Turnstile site in your Cloudflare dashboard and set these in `.env` before the send-code/register endpoints will accept real traffic** — until then every Turnstile check fails closed (empty secret → Cloudflare's siteverify call fails). Tests mock `verify_turnstile_token`, so the test suite does not need real keys.
- `date_of_birth` on `CustomUser`: optional (`null=True, blank=True`), no minimum-age validation.
- No anonymous booking: `ReservationPage` keeps `LoginRequiredMixin` unchanged. The modal is a client-side click-intercept on links, not a change to that view.
- Google OAuth ("Continue with Google") is explicitly out of scope — do not add a Google button or any `django-allauth` wiring in this plan.
- Every new user-facing string goes through `python manage.py makemessages -l bg -l en`, gets a translation in both `locale/bg/LC_MESSAGES/django.po` and `locale/en/LC_MESSAGES/django.po`, then `python manage.py compilemessages` (final task, after all strings exist).
- Test commands: `python manage.py test massageProject.accounts.tests` and `python manage.py test massageProject.main_app.tests` (from the project root, with `venv` activated). Individual new test modules can be run directly, e.g. `python manage.py test massageProject.accounts.tests_email_otp -v 2`.

---

### Task 1: `date_of_birth` field on `CustomUser`

**Files:**
- Modify: `massageProject/massageProject/accounts/models.py`
- Modify: `massageProject/massageProject/accounts/admin.py`
- Test: `massageProject/massageProject/accounts/tests_date_of_birth.py` (create)
- Create: migration via `makemigrations` (auto-generated, e.g. `massageProject/massageProject/accounts/migrations/0006_customuser_date_of_birth.py`)

**Interfaces:**
- Produces: `CustomUser.date_of_birth` (`DateField`, `null=True`, `blank=True`) — consumed by `BookingRegistrationForm` in Task 7.

- [ ] **Step 1: Write the failing test**

Create `massageProject/massageProject/accounts/tests_date_of_birth.py`:
```python
from django.contrib.auth import get_user_model
from django.test import TestCase

User = get_user_model()


class DateOfBirthFieldTest(TestCase):
    def test_user_can_be_created_without_date_of_birth(self):
        user = User.objects.create_user(
            email='nodob@example.com', phone_number='0888700001', password='pass1234',
        )
        self.assertIsNone(user.date_of_birth)

    def test_user_can_store_a_date_of_birth(self):
        user = User.objects.create_user(
            email='withdob@example.com', phone_number='0888700002', password='pass1234',
        )
        user.date_of_birth = '1990-05-20'
        user.save(update_fields=['date_of_birth'])
        user.refresh_from_db()
        self.assertEqual(str(user.date_of_birth), '1990-05-20')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test massageProject.accounts.tests_date_of_birth -v 2`
Expected: FAIL with `AttributeError: 'CustomUser' object has no attribute 'date_of_birth'`

- [ ] **Step 3: Add the field, migrate, update admin**

In `massageProject/massageProject/accounts/models.py`, add the field to `CustomUser` right after the `phone_number` field block (before `is_staff`):
```python
    date_of_birth = models.DateField(
        _("date of birth"),
        null=True,
        blank=True,
    )
```

Run: `python manage.py makemigrations accounts`
Expected: a new migration file created adding `date_of_birth` to `CustomUser`.

Run: `python manage.py migrate accounts`
Expected: `Applying massageProject.accounts.00XX_customuser_date_of_birth... OK`

In `massageProject/massageProject/accounts/admin.py`, update the "Personal Information" fieldset:
```python
        ("Personal Information", {"fields": ("first_name", "last_name", "phone_number", "date_of_birth")}),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test massageProject.accounts.tests_date_of_birth -v 2`
Expected: `OK` (2 tests)

- [ ] **Step 5: Commit**

```bash
git add massageProject/massageProject/accounts/models.py massageProject/massageProject/accounts/admin.py massageProject/massageProject/accounts/migrations/ massageProject/massageProject/accounts/tests_date_of_birth.py
git commit -m "feat: add optional date_of_birth field to CustomUser"
```

---

### Task 2: `EmailOTP` model

**Files:**
- Modify: `massageProject/massageProject/accounts/models.py`
- Test: `massageProject/massageProject/accounts/tests_email_otp.py` (create)
- Create: migration via `makemigrations`

**Interfaces:**
- Produces: `EmailOTP.objects.create_for_email(email, purpose) -> (EmailOTP, code_str)`, `EmailOTP.objects.live_for_email(email) -> QuerySet`, `EmailOTP.verify(email, code) -> (EmailOTP_or_None, error_str_or_None)` where `error_str` is `'no_code'` or `'invalid_code'`, `EmailOTP.PURPOSE_SIGNUP` / `EmailOTP.PURPOSE_LOGIN` constants. Consumed by `booking_auth_views.py` in Tasks 4/5/6.

- [ ] **Step 1: Write the failing test**

Create `massageProject/massageProject/accounts/tests_email_otp.py`:
```python
from django.test import TestCase
from django.utils import timezone

from massageProject.accounts.models import EmailOTP


class EmailOTPTest(TestCase):
    def test_create_for_email_returns_plaintext_code_but_stores_hash_only(self):
        otp, code = EmailOTP.objects.create_for_email('new@example.com', EmailOTP.PURPOSE_SIGNUP)
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())
        self.assertNotEqual(otp.code_hash, code)
        self.assertTrue(otp.check_code(code))

    def test_verify_with_correct_code_marks_consumed(self):
        otp, code = EmailOTP.objects.create_for_email('a@example.com', EmailOTP.PURPOSE_LOGIN)
        matched, error = EmailOTP.verify('a@example.com', code)
        self.assertIsNone(error)
        self.assertEqual(matched.pk, otp.pk)
        matched.refresh_from_db()
        self.assertIsNotNone(matched.consumed_at)

    def test_verify_with_wrong_code_increments_attempts_and_fails(self):
        EmailOTP.objects.create_for_email('b@example.com', EmailOTP.PURPOSE_LOGIN)
        matched, error = EmailOTP.verify('b@example.com', '000000')
        self.assertIsNone(matched)
        self.assertEqual(error, 'invalid_code')
        otp = EmailOTP.objects.live_for_email('b@example.com').first()
        self.assertEqual(otp.attempts, 1)

    def test_verify_with_no_code_sent_returns_no_code_error(self):
        matched, error = EmailOTP.verify('nocode@example.com', '123456')
        self.assertIsNone(matched)
        self.assertEqual(error, 'no_code')

    def test_expired_code_is_not_live(self):
        otp, code = EmailOTP.objects.create_for_email('c@example.com', EmailOTP.PURPOSE_SIGNUP)
        otp.expires_at = timezone.now() - timezone.timedelta(minutes=1)
        otp.save(update_fields=['expires_at'])
        matched, error = EmailOTP.verify('c@example.com', code)
        self.assertIsNone(matched)
        self.assertEqual(error, 'no_code')

    def test_code_becomes_dead_after_five_wrong_attempts(self):
        otp, code = EmailOTP.objects.create_for_email('d@example.com', EmailOTP.PURPOSE_SIGNUP)
        for _ in range(5):
            EmailOTP.verify('d@example.com', '000000')
        matched, error = EmailOTP.verify('d@example.com', code)
        self.assertIsNone(matched)
        self.assertEqual(error, 'no_code')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test massageProject.accounts.tests_email_otp -v 2`
Expected: FAIL with `ImportError: cannot import name 'EmailOTP'`

- [ ] **Step 3: Add the model**

In `massageProject/massageProject/accounts/models.py`, add near the top of the imports:
```python
import random

from django.contrib.auth.hashers import make_password, check_password
```

Append at the end of the file:
```python
OTP_EXPIRY_MINUTES = 10
OTP_MAX_ATTEMPTS = 5


class EmailOTPManager(models.Manager):
    def create_for_email(self, email, purpose):
        code = f"{random.randint(0, 999999):06d}"
        otp = self.create(
            email=email,
            code_hash=make_password(code),
            purpose=purpose,
            expires_at=timezone.now() + timezone.timedelta(minutes=OTP_EXPIRY_MINUTES),
        )
        return otp, code

    def live_for_email(self, email):
        return self.filter(
            email__iexact=email,
            consumed_at__isnull=True,
            attempts__lt=OTP_MAX_ATTEMPTS,
            expires_at__gt=timezone.now(),
        ).order_by('-created_at')


class EmailOTP(models.Model):
    PURPOSE_SIGNUP = 'signup'
    PURPOSE_LOGIN = 'login'
    PURPOSE_CHOICES = [
        (PURPOSE_SIGNUP, _('Signup')),
        (PURPOSE_LOGIN, _('Login')),
    ]

    email = models.EmailField(db_index=True)
    code_hash = models.CharField(max_length=128)
    purpose = models.CharField(max_length=10, choices=PURPOSE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)

    objects = EmailOTPManager()

    def check_code(self, code):
        return check_password(code, self.code_hash)

    @classmethod
    def verify(cls, email, code):
        """
        Returns (otp, error). error is None on success, or 'no_code' /
        'invalid_code' on failure. On success the matched row is stamped
        consumed_at; on mismatch its attempts counter is incremented.
        """
        otp = cls.objects.live_for_email(email).first()
        if otp is None:
            return None, 'no_code'
        if otp.check_code(code):
            otp.consumed_at = timezone.now()
            otp.save(update_fields=['consumed_at'])
            return otp, None
        otp.attempts += 1
        otp.save(update_fields=['attempts'])
        return None, 'invalid_code'
```

Run: `python manage.py makemigrations accounts`
Expected: a new migration creating the `EmailOTP` model.

Run: `python manage.py migrate accounts`
Expected: `Applying massageProject.accounts.00XX_emailotp... OK`

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test massageProject.accounts.tests_email_otp -v 2`
Expected: `OK` (6 tests)

- [ ] **Step 5: Commit**

```bash
git add massageProject/massageProject/accounts/models.py massageProject/massageProject/accounts/migrations/ massageProject/massageProject/accounts/tests_email_otp.py
git commit -m "feat: add EmailOTP model for one-time email codes"
```

---

### Task 3: Cloudflare Turnstile verification helper

**Files:**
- Create: `massageProject/massageProject/accounts/turnstile.py`
- Modify: `massageProject/massageProject/settings.py`
- Test: `massageProject/massageProject/accounts/tests_turnstile.py` (create)

**Interfaces:**
- Produces: `verify_turnstile_token(token, remote_ip=None) -> bool`, `settings.TURNSTILE_SITE_KEY`, `settings.TURNSTILE_SECRET_KEY`. Consumed by `booking_auth_views.py` (Tasks 5 and 8) and `partials/auth_modal.html` (Task 10).

- [ ] **Step 1: Write the failing test**

Create `massageProject/massageProject/accounts/tests_turnstile.py`:
```python
from unittest.mock import patch, Mock

import requests
from django.test import TestCase, override_settings

from massageProject.accounts.turnstile import verify_turnstile_token


@override_settings(TURNSTILE_SECRET_KEY='test-secret')
class VerifyTurnstileTokenTest(TestCase):
    def test_empty_token_fails_without_calling_api(self):
        with patch('massageProject.accounts.turnstile.requests.post') as mock_post:
            self.assertFalse(verify_turnstile_token(''))
            mock_post.assert_not_called()

    @patch('massageProject.accounts.turnstile.requests.post')
    def test_successful_verification_returns_true(self, mock_post):
        mock_post.return_value = Mock(json=lambda: {'success': True})
        self.assertTrue(verify_turnstile_token('good-token'))

    @patch('massageProject.accounts.turnstile.requests.post')
    def test_failed_verification_returns_false(self, mock_post):
        mock_post.return_value = Mock(json=lambda: {'success': False})
        self.assertFalse(verify_turnstile_token('bad-token'))

    @patch('massageProject.accounts.turnstile.requests.post')
    def test_network_error_returns_false(self, mock_post):
        mock_post.side_effect = requests.RequestException('boom')
        self.assertFalse(verify_turnstile_token('token'))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test massageProject.accounts.tests_turnstile -v 2`
Expected: FAIL with `ModuleNotFoundError: No module named 'massageProject.accounts.turnstile'`

- [ ] **Step 3: Add the helper and settings**

Create `massageProject/massageProject/accounts/turnstile.py`:
```python
import requests
from django.conf import settings

TURNSTILE_VERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'


def verify_turnstile_token(token, remote_ip=None):
    if not token:
        return False

    payload = {'secret': settings.TURNSTILE_SECRET_KEY, 'response': token}
    if remote_ip:
        payload['remoteip'] = remote_ip

    try:
        response = requests.post(TURNSTILE_VERIFY_URL, data=payload, timeout=5)
        response.raise_for_status()
    except requests.RequestException:
        return False

    return bool(response.json().get('success'))
```

In `massageProject/massageProject/settings.py`, right after the `GMAIL_API_USER_ID` line, add:
```python

# Cloudflare Turnstile (invisible bot-check widget on the booking auth modal)
TURNSTILE_SITE_KEY = env('TURNSTILE_SITE_KEY', default='')
TURNSTILE_SECRET_KEY = env('TURNSTILE_SECRET_KEY', default='')
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test massageProject.accounts.tests_turnstile -v 2`
Expected: `OK` (4 tests)

- [ ] **Step 5: Commit**

```bash
git add massageProject/massageProject/accounts/turnstile.py massageProject/massageProject/settings.py massageProject/massageProject/accounts/tests_turnstile.py
git commit -m "feat: add Cloudflare Turnstile server-side verification helper"
```

---

### Task 4: `check-email/` endpoint

**Files:**
- Create: `massageProject/massageProject/accounts/booking_auth_views.py`
- Modify: `massageProject/massageProject/accounts/urls.py`
- Test: `massageProject/massageProject/accounts/tests_check_email_view.py` (create)

**Interfaces:**
- Consumes: nothing new yet (just `get_user_model()`).
- Produces: URL name `auth_check_email`, view `check_email`. Consumed by the modal JS in Task 10.

- [ ] **Step 1: Write the failing test**

Create `massageProject/massageProject/accounts/tests_check_email_view.py`:
```python
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class CheckEmailViewTest(TestCase):
    def test_existing_email_returns_exists_true(self):
        User.objects.create_user(email='known@example.com', phone_number='0888800001', password='pass1234')
        response = self.client.post(reverse('auth_check_email'), {'email': 'known@example.com'})
        data = response.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['exists'])

    def test_unknown_email_returns_exists_false(self):
        response = self.client.post(reverse('auth_check_email'), {'email': 'unknown@example.com'})
        data = response.json()
        self.assertTrue(data['success'])
        self.assertFalse(data['exists'])

    def test_email_lookup_is_case_insensitive(self):
        User.objects.create_user(email='Mixed@Example.com', phone_number='0888800002', password='pass1234')
        response = self.client.post(reverse('auth_check_email'), {'email': 'mixed@example.com'})
        self.assertTrue(response.json()['exists'])

    def test_missing_email_is_rejected(self):
        response = self.client.post(reverse('auth_check_email'), {})
        self.assertEqual(response.status_code, 400)

    def test_get_is_not_allowed(self):
        response = self.client.get(reverse('auth_check_email'))
        self.assertEqual(response.status_code, 405)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test massageProject.accounts.tests_check_email_view -v 2`
Expected: FAIL with `NoReverseMatch: Reverse for 'auth_check_email' not found`

- [ ] **Step 3: Add the view and URL**

Create `massageProject/massageProject/accounts/booking_auth_views.py`:
```python
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

User = get_user_model()


@require_POST
def check_email(request):
    email = request.POST.get('email', '').strip().lower()
    if not email:
        return JsonResponse({'success': False, 'error': _('Въведете имейл адрес.')}, status=400)
    exists = User.objects.filter(email__iexact=email).exists()
    return JsonResponse({'success': True, 'exists': exists})
```

In `massageProject/massageProject/accounts/urls.py`, add the import and a URL entry (keep everything else in the file unchanged for now):
```python
from massageProject.accounts.booking_auth_views import check_email
```
Add inside `urlpatterns`, right after the `register/` line:
```python
    path('auth-modal/check-email/', check_email, name='auth_check_email'),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test massageProject.accounts.tests_check_email_view -v 2`
Expected: `OK` (5 tests)

- [ ] **Step 5: Commit**

```bash
git add massageProject/massageProject/accounts/booking_auth_views.py massageProject/massageProject/accounts/urls.py massageProject/massageProject/accounts/tests_check_email_view.py
git commit -m "feat: add check-email endpoint for the booking auth modal"
```

---

### Task 5: `send-code/` endpoint (+ `django-ratelimit` dependency, `send_otp_email`, OTP email templates)

**Files:**
- Modify: `requirements.txt`
- Modify: `massageProject/massageProject/accounts/booking_auth_views.py`
- Modify: `massageProject/massageProject/accounts/urls.py`
- Modify: `massageProject/massageProject/accounts/emails.py`
- Create: `templates/emails/otp_email_subject.txt`
- Create: `templates/emails/otp_email.txt`
- Create: `templates/emails/otp_email.html`
- Test: `massageProject/massageProject/accounts/tests_send_code_view.py` (create)

**Interfaces:**
- Consumes: `EmailOTP.objects.create_for_email` (Task 2), `verify_turnstile_token` (Task 3).
- Produces: URL name `auth_send_code`, view `send_code`; `send_otp_email(request, email, code)` in `emails.py`. Consumed by modal JS (Task 10) and `verify_code` (Task 6, indirectly via the same OTP rows).

- [ ] **Step 1: Write the failing test**

Create `massageProject/massageProject/accounts/tests_send_code_view.py`:
```python
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from massageProject.accounts.models import EmailOTP

User = get_user_model()

TURNSTILE_PATCH = 'massageProject.accounts.booking_auth_views.verify_turnstile_token'


class SendCodeViewTest(TestCase):
    def setUp(self):
        cache.clear()

    @patch(TURNSTILE_PATCH, return_value=True)
    def test_sends_an_email_with_a_code_for_a_new_signup(self, mock_turnstile):
        response = self.client.post(reverse('auth_send_code'), {
            'email': 'newsignup@example.com', 'turnstile_token': 'good',
        })
        self.assertTrue(response.json()['success'])
        self.assertEqual(len(mail.outbox), 1)
        otp = EmailOTP.objects.live_for_email('newsignup@example.com').first()
        self.assertIsNotNone(otp)
        self.assertEqual(otp.purpose, EmailOTP.PURPOSE_SIGNUP)

    @patch(TURNSTILE_PATCH, return_value=True)
    def test_purpose_is_login_for_an_existing_users_email(self, mock_turnstile):
        User.objects.create_user(email='existing@example.com', phone_number='0888930001', password='pass1234')
        self.client.post(reverse('auth_send_code'), {
            'email': 'existing@example.com', 'turnstile_token': 'good',
        })
        otp = EmailOTP.objects.live_for_email('existing@example.com').first()
        self.assertEqual(otp.purpose, EmailOTP.PURPOSE_LOGIN)

    @patch(TURNSTILE_PATCH, return_value=False)
    def test_failed_turnstile_check_is_rejected_and_sends_no_email(self, mock_turnstile):
        response = self.client.post(reverse('auth_send_code'), {
            'email': 'suspicious@example.com', 'turnstile_token': 'bad',
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(mail.outbox), 0)

    @patch(TURNSTILE_PATCH, return_value=True)
    def test_sixth_request_from_the_same_ip_within_a_minute_is_rate_limited(self, mock_turnstile):
        for i in range(5):
            resp = self.client.post(reverse('auth_send_code'), {
                'email': 'ratelimit{}@example.com'.format(i), 'turnstile_token': 'good',
            })
            self.assertEqual(resp.status_code, 200)
        resp = self.client.post(reverse('auth_send_code'), {
            'email': 'ratelimitX@example.com', 'turnstile_token': 'good',
        })
        self.assertEqual(resp.status_code, 429)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test massageProject.accounts.tests_send_code_view -v 2`
Expected: FAIL with `NoReverseMatch: Reverse for 'auth_send_code' not found`

- [ ] **Step 3: Install the dependency, add the view, the email function and templates**

Install and pin the dependency:
```bash
source venv/bin/activate
pip install django-ratelimit==4.1.0
```

In `requirements.txt`, insert alphabetically (between `django-modeltranslation` and `django-rosetta`):
```
django-ratelimit==4.1.0
```

Create `templates/emails/otp_email_subject.txt`:
```
{% load i18n %}{% trans "Ваш код за потвърждение" %}
```

Create `templates/emails/otp_email.txt`:
```
{% load i18n %}{% trans "Здравейте," %}

{% trans "Използвайте следния код, за да потвърдите своя имейл адрес:" %}
{{ code }}

{% trans "Кодът е валиден 10 минути." %}
{% trans "Ако не сте поискали този код, можете да игнорирате този имейл." %}
```

Create `templates/emails/otp_email.html`:
```
{% extends "emails/base_email.html" %}
{% load i18n %}
{% block subject %}{% trans "Ваш код за потвърждение" %}{% endblock %}
{% block content %}
<h1 style="font-family:'Playfair Display', Georgia, serif; font-size:22px; color:#4A3728; margin:0 0 16px;">{% trans "Здравейте," %}</h1>
<p style="font-size:15px; line-height:1.6; margin:0 0 24px;">{% trans "Използвайте следния код, за да потвърдите своя имейл адрес:" %}</p>
<p style="text-align:center; margin:0 0 24px;">
  <span style="display:inline-block; background-color:#F2EBE2; color:#4A3728; letter-spacing:0.3em; font-size:28px; font-weight:700; padding:14px 24px; border-radius:8px;">{{ code }}</span>
</p>
<p style="font-size:13px; color:#6B5E55; margin:0 0 4px;">{% trans "Кодът е валиден 10 минути." %}</p>
<p style="font-size:13px; color:#6B5E55; margin:0;">{% trans "Ако не сте поискали този код, можете да игнорирате този имейл." %}</p>
{% endblock %}
```

In `massageProject/massageProject/accounts/emails.py`, append:
```python
def send_otp_email(request, email, code):
    from massageProject.main_app.models import HomePage

    homepage = HomePage.get_solo()
    logo_url = None
    if homepage and homepage.logo:
        logo_url = request.build_absolute_uri(homepage.logo.url)

    context = {
        'code': code,
        'brand_name': homepage.brand_name if homepage else _('Relax & Health'),
        'logo_url': logo_url,
    }
    subject = render_to_string('emails/otp_email_subject.txt', context).strip()
    text_body = render_to_string('emails/otp_email.txt', context)
    html_body = render_to_string('emails/otp_email.html', context)

    message = EmailMultiAlternatives(subject, text_body, settings.DEFAULT_FROM_EMAIL, [email])
    message.attach_alternative(html_body, 'text/html')
    message.send()
```

In `massageProject/massageProject/accounts/booking_auth_views.py`, update the imports and add the view:
```python
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from massageProject.accounts.emails import send_otp_email
from massageProject.accounts.models import EmailOTP
from massageProject.accounts.turnstile import verify_turnstile_token

User = get_user_model()
```
Add below `check_email`:
```python
@require_POST
@ratelimit(key='ip', rate='5/m', block=False)
@ratelimit(key='post:email', rate='3/m', block=False)
def send_code(request):
    if request.limited:
        return JsonResponse({'success': False, 'error': _('Твърде много опити. Опитайте отново по-късно.')}, status=429)

    email = request.POST.get('email', '').strip().lower()
    turnstile_token = request.POST.get('turnstile_token', '')

    if not email:
        return JsonResponse({'success': False, 'error': _('Въведете имейл адрес.')}, status=400)

    if not verify_turnstile_token(turnstile_token, remote_ip=request.META.get('REMOTE_ADDR')):
        return JsonResponse({'success': False, 'error': _('Проверката за робот не е успешна. Опитайте отново.')}, status=400)

    purpose = EmailOTP.PURPOSE_LOGIN if User.objects.filter(email__iexact=email).exists() else EmailOTP.PURPOSE_SIGNUP
    otp, code = EmailOTP.objects.create_for_email(email, purpose)
    send_otp_email(request, email, code)

    return JsonResponse({'success': True})
```

In `massageProject/massageProject/accounts/urls.py`, update the import and add the URL:
```python
from massageProject.accounts.booking_auth_views import check_email, send_code
```
```python
    path('auth-modal/send-code/', send_code, name='auth_send_code'),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test massageProject.accounts.tests_send_code_view -v 2`
Expected: `OK` (4 tests)

- [ ] **Step 5: Commit**

```bash
git add requirements.txt massageProject/massageProject/accounts/booking_auth_views.py massageProject/massageProject/accounts/urls.py massageProject/massageProject/accounts/emails.py templates/emails/otp_email_subject.txt templates/emails/otp_email.txt templates/emails/otp_email.html massageProject/massageProject/accounts/tests_send_code_view.py
git commit -m "feat: add send-code endpoint with rate limiting and Turnstile check"
```

---

### Task 6: `verify-code/` endpoint

**Files:**
- Modify: `massageProject/massageProject/accounts/booking_auth_views.py`
- Modify: `massageProject/massageProject/accounts/urls.py`
- Test: `massageProject/massageProject/accounts/tests_verify_code_view.py` (create)

**Interfaces:**
- Consumes: `EmailOTP.verify` (Task 2), `CustomAuthenticationForm.error_messages['inactive']` (existing, `forms.py`).
- Produces: URL name `auth_verify_code`, view `verify_code`, module-level constants `SIGNUP_EMAIL_SESSION_KEY = 'verified_signup_email'` and `SIGNUP_EMAIL_SESSION_TTL_SECONDS = 15 * 60` in `booking_auth_views.py` — consumed by `register_via_modal` (Task 8).

- [ ] **Step 1: Write the failing test**

Create `massageProject/massageProject/accounts/tests_verify_code_view.py`:
```python
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from massageProject.accounts.models import EmailOTP

User = get_user_model()


class VerifyCodeViewTest(TestCase):
    def setUp(self):
        cache.clear()

    def test_correct_code_for_new_email_marks_session_verified(self):
        from massageProject.accounts.booking_auth_views import SIGNUP_EMAIL_SESSION_KEY

        otp, code = EmailOTP.objects.create_for_email('newuser@example.com', EmailOTP.PURPOSE_SIGNUP)
        response = self.client.post(reverse('auth_verify_code'), {'email': 'newuser@example.com', 'code': code})
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['status'], 'verified')
        self.assertEqual(self.client.session.get(SIGNUP_EMAIL_SESSION_KEY), 'newuser@example.com')

    def test_correct_code_for_existing_active_user_logs_in(self):
        User.objects.create_user(email='existing@example.com', phone_number='0888940001', password='pass1234')
        otp, code = EmailOTP.objects.create_for_email('existing@example.com', EmailOTP.PURPOSE_LOGIN)
        response = self.client.post(reverse('auth_verify_code'), {'email': 'existing@example.com', 'code': code})
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['status'], 'logged_in')
        resp = self.client.get(reverse('profile_page'))
        self.assertTrue(resp.wsgi_request.user.is_authenticated)

    def test_correct_code_for_inactive_existing_user_is_blocked(self):
        user = User.objects.create_user(email='inactive@example.com', phone_number='0888940002', password='pass1234')
        user.is_active = False
        user.save(update_fields=['is_active'])
        otp, code = EmailOTP.objects.create_for_email('inactive@example.com', EmailOTP.PURPOSE_LOGIN)
        response = self.client.post(reverse('auth_verify_code'), {'email': 'inactive@example.com', 'code': code})
        data = response.json()
        self.assertFalse(data['success'])
        resp = self.client.get(reverse('profile_page'))
        self.assertFalse(resp.wsgi_request.user.is_authenticated)

    def test_wrong_code_is_rejected(self):
        EmailOTP.objects.create_for_email('a@example.com', EmailOTP.PURPOSE_SIGNUP)
        response = self.client.post(reverse('auth_verify_code'), {'email': 'a@example.com', 'code': '000000'})
        self.assertFalse(response.json()['success'])

    def test_no_code_requested_is_rejected(self):
        response = self.client.post(reverse('auth_verify_code'), {'email': 'never@example.com', 'code': '123456'})
        self.assertFalse(response.json()['success'])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test massageProject.accounts.tests_verify_code_view -v 2`
Expected: FAIL with `NoReverseMatch: Reverse for 'auth_verify_code' not found`

- [ ] **Step 3: Add the view and URL**

In `massageProject/massageProject/accounts/booking_auth_views.py`, update imports:
```python
from django.contrib.auth import get_user_model, login
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from massageProject.accounts.emails import send_otp_email
from massageProject.accounts.forms import CustomAuthenticationForm
from massageProject.accounts.models import EmailOTP
from massageProject.accounts.turnstile import verify_turnstile_token

User = get_user_model()

SIGNUP_EMAIL_SESSION_KEY = 'verified_signup_email'
SIGNUP_EMAIL_SESSION_TTL_SECONDS = 15 * 60
```
Add below `send_code`:
```python
@require_POST
@ratelimit(key='ip', rate='10/m', block=False)
@ratelimit(key='post:email', rate='8/m', block=False)
def verify_code(request):
    if request.limited:
        return JsonResponse({'success': False, 'error': _('Твърде много опити. Опитайте отново по-късно.')}, status=429)

    email = request.POST.get('email', '').strip().lower()
    code = request.POST.get('code', '').strip()
    next_url = request.POST.get('next') or reverse('reservation_page')

    if not email or not code:
        return JsonResponse({'success': False, 'error': _('Въведете имейл и код.')}, status=400)

    otp, error = EmailOTP.verify(email, code)
    if error:
        message = (
            _('Кодът е грешен или е изтекъл.') if error == 'invalid_code'
            else _('Няма активен код за този имейл. Изпратете нов.')
        )
        return JsonResponse({'success': False, 'error': str(message)}, status=400)

    try:
        user = User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        request.session[SIGNUP_EMAIL_SESSION_KEY] = email
        request.session[SIGNUP_EMAIL_SESSION_KEY + '_expires'] = (
            timezone.now() + timezone.timedelta(seconds=SIGNUP_EMAIL_SESSION_TTL_SECONDS)
        ).isoformat()
        return JsonResponse({'success': True, 'status': 'verified', 'next': 'register'})

    if not user.is_active:
        return JsonResponse({
            'success': False,
            'error': str(CustomAuthenticationForm.error_messages['inactive']),
        }, status=403)

    login(request, user, backend='massageProject.accounts.backends.VerificationAwareBackend')
    return JsonResponse({'success': True, 'status': 'logged_in', 'redirect': next_url})
```

In `massageProject/massageProject/accounts/urls.py`:
```python
from massageProject.accounts.booking_auth_views import check_email, send_code, verify_code
```
```python
    path('auth-modal/verify-code/', verify_code, name='auth_verify_code'),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test massageProject.accounts.tests_verify_code_view -v 2`
Expected: `OK` (5 tests)

- [ ] **Step 5: Commit**

```bash
git add massageProject/massageProject/accounts/booking_auth_views.py massageProject/massageProject/accounts/urls.py massageProject/massageProject/accounts/tests_verify_code_view.py
git commit -m "feat: add verify-code endpoint branching into login or signup"
```

---

### Task 7: `PhoneClaimFormMixin` + `BookingRegistrationForm`

**Files:**
- Modify: `massageProject/massageProject/accounts/forms.py`
- Test: `massageProject/massageProject/accounts/tests_booking_registration_form.py` (create)

**Interfaces:**
- Consumes: `CustomUser.date_of_birth` (Task 1), `User.objects.normalize_phone_number` (existing, `managers.py`).
- Produces: `BookingRegistrationForm(data=..., email=...)` — fields `first_name`, `last_name`, `phone_number`, `password`, `date_of_birth` (optional), `middle_name` (honeypot, always optional); `.save()` returns an active `CustomUser` with `email` set from the constructor's `email` kwarg. Consumed by `register_via_modal` in Task 8.

- [ ] **Step 1: Write the failing test**

Create `massageProject/massageProject/accounts/tests_booking_registration_form.py`:
```python
from django.contrib.auth import get_user_model
from django.test import TestCase

from massageProject.accounts.forms import BookingRegistrationForm

User = get_user_model()


class BookingRegistrationFormTest(TestCase):
    VALID_DATA = {
        'first_name': 'Maria',
        'last_name': 'Ivanova',
        'phone_number': '0888900001',
        'password': 'ComplexPass!123',
    }

    def test_valid_data_creates_an_active_user_with_the_verified_email(self):
        form = BookingRegistrationForm(data=self.VALID_DATA, email='verified@example.com')
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.email, 'verified@example.com')
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password('ComplexPass!123'))

    def test_missing_email_is_invalid(self):
        form = BookingRegistrationForm(data=self.VALID_DATA, email=None)
        self.assertFalse(form.is_valid())

    def test_requires_first_and_last_name(self):
        data = {**self.VALID_DATA, 'first_name': '', 'last_name': ''}
        form = BookingRegistrationForm(data=data, email='verified2@example.com')
        self.assertFalse(form.is_valid())
        self.assertIn('first_name', form.errors)
        self.assertIn('last_name', form.errors)

    def test_date_of_birth_is_optional(self):
        form = BookingRegistrationForm(data=self.VALID_DATA, email='verified3@example.com')
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertIsNone(user.date_of_birth)

    def test_date_of_birth_can_be_provided(self):
        data = {**self.VALID_DATA, 'phone_number': '0888900002', 'date_of_birth': '1990-05-20'}
        form = BookingRegistrationForm(data=data, email='verified4@example.com')
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(str(user.date_of_birth), '1990-05-20')

    def test_phone_belonging_to_passwordless_user_is_claimed(self):
        existing = User.objects.create(email='placeholder@example.com', phone_number='0888900003')
        existing.set_unusable_password()
        existing.save()

        data = {**self.VALID_DATA, 'phone_number': '0888900003'}
        form = BookingRegistrationForm(data=data, email='claimed@example.com')
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.pk, existing.pk)
        self.assertEqual(user.email, 'claimed@example.com')
        self.assertTrue(user.check_password('ComplexPass!123'))

    def test_phone_belonging_to_a_user_with_a_password_is_rejected(self):
        User.objects.create_user(email='taken@example.com', phone_number='0888900004', password='pass1234')
        data = {**self.VALID_DATA, 'phone_number': '0888900004'}
        form = BookingRegistrationForm(data=data, email='new@example.com')
        self.assertFalse(form.is_valid())
        self.assertIn('phone_number', form.errors)

    def test_weak_password_is_rejected(self):
        data = {**self.VALID_DATA, 'phone_number': '0888900005', 'password': '123'}
        form = BookingRegistrationForm(data=data, email='weakpass@example.com')
        self.assertFalse(form.is_valid())
        self.assertIn('password', form.errors)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test massageProject.accounts.tests_booking_registration_form -v 2`
Expected: FAIL with `ImportError: cannot import name 'BookingRegistrationForm'`

- [ ] **Step 3: Add the mixin and form**

In `massageProject/massageProject/accounts/forms.py`, add these imports at the top (alongside the existing ones):
```python
from django.contrib.auth.password_validation import validate_password
```
Append at the end of the file:
```python
class PhoneClaimFormMixin:
    """
    If a phone number already belongs to a passwordless (e.g. staff-created)
    user record, attach that record as self.instance so saving the form
    updates/"claims" it instead of failing the uniqueness check.
    """
    error_messages = {
        'already_registered': _('Този телефонен номер вече е регистриран. Моля, влезте в профила си.'),
    }

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if not phone_number:
            return phone_number

        User = get_user_model()
        normalized_phone = User.objects.normalize_phone_number(phone_number)

        try:
            existing_user = User.objects.get(phone_number__iexact=normalized_phone)
            if existing_user.has_usable_password():
                raise ValidationError(self.error_messages['already_registered'])
            self.instance = existing_user
        except User.DoesNotExist:
            pass

        return normalized_phone


class BookingRegistrationForm(PhoneClaimFormMixin, forms.ModelForm):
    password = forms.CharField(
        label=_('Парола'),
        strip=False,
        widget=forms.PasswordInput,
    )
    middle_name = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = get_user_model()
        fields = ('first_name', 'last_name', 'phone_number', 'date_of_birth')

    def __init__(self, *args, email=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._email = email
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        self.fields['date_of_birth'].required = False
        self.fields['phone_number'].widget.attrs.update({'placeholder': '0899999999'})
        for field in self.fields.values():
            field.help_text = None

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if password:
            validate_password(password, self.instance)
        return password

    def clean(self):
        cleaned_data = super().clean()
        if not self._email:
            raise ValidationError(_('Имейлът не е потвърден.'))
        return cleaned_data

    def save(self, commit=True):
        # The claimed/new instance may not have had its email set yet, or may
        # have had a placeholder one -- the verified session email always wins.
        user = super().save(commit=False)
        user.email = self._email
        user.is_active = True
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test massageProject.accounts.tests_booking_registration_form -v 2`
Expected: `OK` (8 tests)

- [ ] **Step 5: Commit**

```bash
git add massageProject/massageProject/accounts/forms.py massageProject/massageProject/accounts/tests_booking_registration_form.py
git commit -m "feat: add BookingRegistrationForm for the auth modal signup step"
```

---

### Task 8: `register/` endpoint

**Files:**
- Modify: `massageProject/massageProject/accounts/booking_auth_views.py`
- Modify: `massageProject/massageProject/accounts/urls.py`
- Test: `massageProject/massageProject/accounts/tests_register_view.py` (create)

**Interfaces:**
- Consumes: `BookingRegistrationForm` (Task 7), `SIGNUP_EMAIL_SESSION_KEY`/`SIGNUP_EMAIL_SESSION_TTL_SECONDS` (Task 6), `verify_turnstile_token` (Task 3).
- Produces: URL name `auth_register`, view `register_via_modal`. Consumed by modal JS (Task 10).

- [ ] **Step 1: Write the failing test**

Create `massageProject/massageProject/accounts/tests_register_view.py`:
```python
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

User = get_user_model()

TURNSTILE_PATCH = 'massageProject.accounts.booking_auth_views.verify_turnstile_token'


class RegisterViewTest(TestCase):
    def setUp(self):
        cache.clear()

    def _session_with_verified_email(self, email):
        from massageProject.accounts.booking_auth_views import SIGNUP_EMAIL_SESSION_KEY

        session = self.client.session
        session[SIGNUP_EMAIL_SESSION_KEY] = email
        session[SIGNUP_EMAIL_SESSION_KEY + '_expires'] = (
            timezone.now() + timezone.timedelta(minutes=15)
        ).isoformat()
        session.save()

    @patch(TURNSTILE_PATCH, return_value=True)
    def test_valid_submission_creates_active_logged_in_user(self, mock_turnstile):
        self._session_with_verified_email('newbooker@example.com')
        response = self.client.post(reverse('auth_register'), {
            'first_name': 'Petar', 'last_name': 'Georgiev',
            'phone_number': '0888910001', 'password': 'ComplexPass!123',
            'turnstile_token': 'ok',
        })
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['status'], 'registered')

        user = User.objects.get(email='newbooker@example.com')
        self.assertTrue(user.is_active)

        resp = self.client.get(reverse('profile_page'))
        self.assertTrue(resp.wsgi_request.user.is_authenticated)

    def test_missing_verified_session_is_rejected(self):
        response = self.client.post(reverse('auth_register'), {
            'first_name': 'Petar', 'last_name': 'Georgiev',
            'phone_number': '0888910002', 'password': 'ComplexPass!123',
            'turnstile_token': 'ok',
        })
        self.assertEqual(response.status_code, 403)
        self.assertEqual(User.objects.filter(phone_number='0888910002').count(), 0)

    def test_honeypot_field_filled_returns_fake_success_without_creating_user(self):
        self._session_with_verified_email('bot@example.com')
        response = self.client.post(reverse('auth_register'), {
            'first_name': 'Bot', 'last_name': 'Bot',
            'phone_number': '0888910003', 'password': 'ComplexPass!123',
            'middle_name': 'i-am-a-bot',
            'turnstile_token': 'ok',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertEqual(User.objects.filter(email='bot@example.com').count(), 0)

    @patch(TURNSTILE_PATCH, return_value=False)
    def test_failed_turnstile_check_is_rejected(self, mock_turnstile):
        self._session_with_verified_email('suspicious@example.com')
        response = self.client.post(reverse('auth_register'), {
            'first_name': 'Test', 'last_name': 'User',
            'phone_number': '0888910004', 'password': 'ComplexPass!123',
            'turnstile_token': 'bad',
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(User.objects.filter(email='suspicious@example.com').count(), 0)

    @patch(TURNSTILE_PATCH, return_value=True)
    def test_invalid_form_data_returns_field_errors(self, mock_turnstile):
        self._session_with_verified_email('bad@example.com')
        response = self.client.post(reverse('auth_register'), {
            'first_name': '', 'last_name': '',
            'phone_number': '0888910005', 'password': 'ComplexPass!123',
            'turnstile_token': 'ok',
        })
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('first_name', data['errors'])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test massageProject.accounts.tests_register_view -v 2`
Expected: FAIL with `NoReverseMatch: Reverse for 'auth_register' not found`

- [ ] **Step 3: Add the view and URL**

In `massageProject/massageProject/accounts/booking_auth_views.py`, update imports:
```python
from datetime import datetime

from django.contrib.auth import get_user_model, login
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from massageProject.accounts.emails import send_otp_email
from massageProject.accounts.forms import BookingRegistrationForm, CustomAuthenticationForm
from massageProject.accounts.models import EmailOTP
from massageProject.accounts.turnstile import verify_turnstile_token
```
Add below `verify_code`:
```python
@require_POST
@ratelimit(key='ip', rate='5/m', block=False)
def register_via_modal(request):
    if request.limited:
        return JsonResponse({'success': False, 'error': _('Твърде много опити. Опитайте отново по-късно.')}, status=429)

    next_url = request.POST.get('next') or reverse('reservation_page')

    email = request.session.get(SIGNUP_EMAIL_SESSION_KEY)
    expires_raw = request.session.get(SIGNUP_EMAIL_SESSION_KEY + '_expires')
    if not email or not expires_raw or timezone.now() > datetime.fromisoformat(expires_raw):
        return JsonResponse({'success': False, 'error': _('Имейлът не е потвърден или потвърждението е изтекло.')}, status=403)

    if request.POST.get('middle_name', ''):
        # Honeypot tripped -- pretend success, create nothing.
        return JsonResponse({'success': True, 'status': 'registered', 'redirect': next_url})

    if not verify_turnstile_token(request.POST.get('turnstile_token', ''), remote_ip=request.META.get('REMOTE_ADDR')):
        return JsonResponse({'success': False, 'error': _('Проверката за робот не е успешна. Опитайте отново.')}, status=400)

    form = BookingRegistrationForm(data=request.POST, email=email)
    if not form.is_valid():
        errors = {field: [str(e) for e in errs] for field, errs in form.errors.items()}
        return JsonResponse({'success': False, 'errors': errors}, status=400)

    user = form.save()
    del request.session[SIGNUP_EMAIL_SESSION_KEY]
    del request.session[SIGNUP_EMAIL_SESSION_KEY + '_expires']
    login(request, user, backend='massageProject.accounts.backends.VerificationAwareBackend')

    return JsonResponse({'success': True, 'status': 'registered', 'redirect': next_url})
```

In `massageProject/massageProject/accounts/urls.py`:
```python
from massageProject.accounts.booking_auth_views import check_email, send_code, verify_code, register_via_modal
```
```python
    path('auth-modal/register/', register_via_modal, name='auth_register'),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test massageProject.accounts.tests_register_view -v 2`
Expected: `OK` (5 tests)

- [ ] **Step 5: Commit**

```bash
git add massageProject/massageProject/accounts/booking_auth_views.py massageProject/massageProject/accounts/urls.py massageProject/massageProject/accounts/tests_register_view.py
git commit -m "feat: add register endpoint for the auth modal signup step"
```

---

### Task 9: `login-password/` endpoint (+ migrate inactive-login regression tests)

**Files:**
- Modify: `massageProject/massageProject/accounts/booking_auth_views.py`
- Modify: `massageProject/massageProject/accounts/urls.py`
- Test: `massageProject/massageProject/accounts/tests_login_password_view.py` (create)

**Interfaces:**
- Consumes: `CustomAuthenticationForm` (existing, `forms.py`).
- Produces: URL name `auth_login_password`, view `login_password`. Consumed by modal JS (Task 10).

- [ ] **Step 1: Write the failing test**

Create `massageProject/massageProject/accounts/tests_login_password_view.py`:
```python
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from massageProject.accounts.forms import CustomAuthenticationForm

User = get_user_model()


class LoginPasswordViewTest(TestCase):
    PASSWORD = 'ComplexPass!123'
    WRONG_PASSWORD = 'TotallyWrongPass!456'

    def setUp(self):
        cache.clear()

    def _create_user(self, email, phone_number, is_active):
        user = User.objects.create_user(email=email, phone_number=phone_number, password=self.PASSWORD)
        user.is_active = is_active
        user.save(update_fields=['is_active'])
        return user

    def test_active_user_correct_password_logs_in(self):
        self._create_user('active@example.com', '0888920001', is_active=True)
        response = self.client.post(reverse('auth_login_password'), {
            'email': 'active@example.com', 'password': self.PASSWORD,
        })
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['status'], 'logged_in')

    def test_inactive_user_correct_password_sees_custom_inactive_message(self):
        self._create_user('inactive@example.com', '0888920002', is_active=False)
        response = self.client.post(reverse('auth_login_password'), {
            'email': 'inactive@example.com', 'password': self.PASSWORD,
        })
        data = response.json()
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], str(CustomAuthenticationForm.error_messages['inactive']))

    def test_active_user_wrong_password_sees_generic_message_not_inactive_message(self):
        self._create_user('active2@example.com', '0888920003', is_active=True)
        response = self.client.post(reverse('auth_login_password'), {
            'email': 'active2@example.com', 'password': self.WRONG_PASSWORD,
        })
        data = response.json()
        self.assertFalse(data['success'])
        self.assertNotEqual(data['error'], str(CustomAuthenticationForm.error_messages['inactive']))

    def test_inactive_user_wrong_password_sees_generic_message_not_inactive_message(self):
        self._create_user('inactive2@example.com', '0888920004', is_active=False)
        response = self.client.post(reverse('auth_login_password'), {
            'email': 'inactive2@example.com', 'password': self.WRONG_PASSWORD,
        })
        data = response.json()
        self.assertFalse(data['success'])
        self.assertNotEqual(data['error'], str(CustomAuthenticationForm.error_messages['inactive']))

    def test_logged_in_session_is_established(self):
        self._create_user('sessioncheck@example.com', '0888920005', is_active=True)
        self.client.post(reverse('auth_login_password'), {
            'email': 'sessioncheck@example.com', 'password': self.PASSWORD,
        })
        response = self.client.get(reverse('profile_page'))
        self.assertTrue(response.wsgi_request.user.is_authenticated)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test massageProject.accounts.tests_login_password_view -v 2`
Expected: FAIL with `NoReverseMatch: Reverse for 'auth_login_password' not found`

- [ ] **Step 3: Add the view and URL**

In `massageProject/massageProject/accounts/booking_auth_views.py`, add below `check_email` (order in the file doesn't matter, but keep views grouped logically):
```python
@require_POST
@ratelimit(key='ip', rate='10/m', block=False)
@ratelimit(key='post:email', rate='8/m', block=False)
def login_password(request):
    if request.limited:
        return JsonResponse({'success': False, 'error': _('Твърде много опити. Опитайте отново по-късно.')}, status=429)

    next_url = request.POST.get('next') or reverse('reservation_page')
    form = CustomAuthenticationForm(request, data={
        'username': request.POST.get('email', ''),
        'password': request.POST.get('password', ''),
    })
    if not form.is_valid():
        non_field = [str(e) for e in form.non_field_errors()]
        field_errors = {f: [str(e) for e in errs] for f, errs in form.errors.items() if f != '__all__'}
        return JsonResponse({
            'success': False,
            'error': non_field[0] if non_field else '',
            'errors': field_errors,
        }, status=400)

    login(request, form.get_user())
    return JsonResponse({'success': True, 'status': 'logged_in', 'redirect': next_url})
```

In `massageProject/massageProject/accounts/urls.py`:
```python
from massageProject.accounts.booking_auth_views import (
    check_email, send_code, verify_code, register_via_modal, login_password,
)
```
```python
    path('auth-modal/login-password/', login_password, name='auth_login_password'),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test massageProject.accounts.tests_login_password_view -v 2`
Expected: `OK` (5 tests)

- [ ] **Step 5: Commit**

```bash
git add massageProject/massageProject/accounts/booking_auth_views.py massageProject/massageProject/accounts/urls.py massageProject/massageProject/accounts/tests_login_password_view.py
git commit -m "feat: add login-password endpoint for the auth modal existing-user step"
```

---

### Task 10: Auth modal partial (markup + CSS + JS)

This task builds the modal itself as a standalone, fully-wired component. It is not yet included anywhere in the site — Task 11 wires it into `base.html` and the "Book Now"/header links. There is no Django test-runner coverage for vanilla JS in this codebase (the existing homepage review modal has none either); this task is verified manually at the end via the dev server.

**Files:**
- Create: `massageProject/massageProject/accounts/context_processors.py`
- Modify: `massageProject/massageProject/settings.py`
- Create: `templates/partials/auth_modal.html`
- Create: `staticfiles/css/components/auth-modal.css`
- Modify: `staticfiles/css/styles.css`

**Interfaces:**
- Produces: template context variable `turnstile_site_key` (available on every page); global JS object `window.AuthModal = { open(opts), close() }` where `opts.next` is the post-login redirect URL. Consumed by Task 11's click-intercept and Task 12's `AuthEntryView` template.

- [ ] **Step 1: Add the Turnstile site-key context processor**

Create `massageProject/massageProject/accounts/context_processors.py`:
```python
from django.conf import settings


def turnstile(request):
    return {'turnstile_site_key': settings.TURNSTILE_SITE_KEY}
```

In `massageProject/massageProject/settings.py`, add to `TEMPLATES[0]['OPTIONS']['context_processors']`, right after `'massageProject.main_app.context_processors.admin_branding'`:
```python
                'massageProject.accounts.context_processors.turnstile',
```

- [ ] **Step 2: Create the modal partial (markup, inline script, honeypot, Turnstile widget)**

Create `templates/partials/auth_modal.html`:
```html
{% load i18n %}
{% trans "Въведете имейл адрес." as msg_enter_email %}
{% trans "Възникна грешка. Опитайте отново." as msg_generic_error %}
{% trans "Въведете всичките 6 цифри." as msg_enter_all_digits %}
<div class="auth-modal-overlay" id="auth-modal" aria-hidden="true" role="dialog" aria-modal="true">
  <div class="auth-modal">
    <button type="button" class="auth-modal-close" id="auth-modal-close" aria-label="{% trans "Затвори" %}">&times;</button>
    {% csrf_token %}
    <div class="cf-turnstile" id="auth-turnstile" data-sitekey="{{ turnstile_site_key }}" data-size="invisible" data-callback="authModalTurnstileCallback"></div>

    <div class="auth-modal-step" data-step="email">
      <h2 class="auth-modal-title">{% trans "Влезте или се регистрирайте" %}</h2>
      <p class="auth-modal-subtitle">{% trans "За да завършите резервацията, трябва да потвърдим Вашия имейл." %}</p>
      <div class="auth-modal-field">
        <label class="auth-modal-label" for="auth-email-input">{% trans "Имейл" %}</label>
        <input type="email" id="auth-email-input" class="auth-modal-input" autocomplete="email" placeholder="example@email.com">
      </div>
      <p class="auth-modal-error" id="auth-email-error"></p>
      <button type="button" class="btn btn-primary auth-modal-submit" id="auth-email-continue">{% trans "Продължи" %}</button>
    </div>

    <div class="auth-modal-step" data-step="choice" hidden>
      <h2 class="auth-modal-title">{% trans "Как искате да влезете?" %}</h2>
      <p class="auth-modal-subtitle" id="auth-choice-email"></p>
      <button type="button" class="btn btn-outline auth-modal-submit" id="auth-choice-password">{% trans "С парола" %}</button>
      <button type="button" class="btn btn-outline auth-modal-submit" id="auth-choice-code">{% trans "С код по имейл" %}</button>
    </div>

    <div class="auth-modal-step" data-step="password" hidden>
      <h2 class="auth-modal-title">{% trans "Въведете паролата си" %}</h2>
      <p class="auth-modal-subtitle" id="auth-password-email"></p>
      <div class="auth-modal-field">
        <label class="auth-modal-label" for="auth-password-input">{% trans "Парола" %}</label>
        <input type="password" id="auth-password-input" class="auth-modal-input" autocomplete="current-password">
      </div>
      <p class="auth-modal-error" id="auth-password-error"></p>
      <button type="button" class="btn btn-primary auth-modal-submit" id="auth-password-continue">{% trans "Вход" %}</button>
      <p class="auth-modal-footnote"><a href="{% url 'password_reset' %}">{% trans "Забравена парола?" %}</a></p>
    </div>

    <div class="auth-modal-step" data-step="code" hidden>
      <h2 class="auth-modal-title">{% trans "Потвърдете своя имейл" %}</h2>
      <p class="auth-modal-subtitle" id="auth-code-sent-to"></p>
      <div class="auth-modal-code-inputs" id="auth-code-inputs">
        <input type="text" inputmode="numeric" maxlength="1" class="auth-modal-code-digit">
        <input type="text" inputmode="numeric" maxlength="1" class="auth-modal-code-digit">
        <input type="text" inputmode="numeric" maxlength="1" class="auth-modal-code-digit">
        <input type="text" inputmode="numeric" maxlength="1" class="auth-modal-code-digit">
        <input type="text" inputmode="numeric" maxlength="1" class="auth-modal-code-digit">
        <input type="text" inputmode="numeric" maxlength="1" class="auth-modal-code-digit">
      </div>
      <p class="auth-modal-error" id="auth-code-error"></p>
      <button type="button" class="btn btn-primary auth-modal-submit" id="auth-code-continue">{% trans "Продължи" %}</button>
      <p class="auth-modal-footnote">{% trans "Не получихте код?" %} <button type="button" class="auth-modal-link-btn" id="auth-code-resend">{% trans "Изпрати отново" %}</button></p>
    </div>

    <div class="auth-modal-step" data-step="register" hidden>
      <h2 class="auth-modal-title">{% trans "Създайте профил" %}</h2>
      <div class="auth-modal-field">
        <label class="auth-modal-label" for="auth-register-first-name">{% trans "Име" %}</label>
        <input type="text" id="auth-register-first-name" class="auth-modal-input">
      </div>
      <div class="auth-modal-field">
        <label class="auth-modal-label" for="auth-register-last-name">{% trans "Фамилия" %}</label>
        <input type="text" id="auth-register-last-name" class="auth-modal-input">
      </div>
      <div class="auth-modal-field">
        <label class="auth-modal-label" for="auth-register-phone">{% trans "Телефон" %}</label>
        <input type="text" id="auth-register-phone" class="auth-modal-input" placeholder="0899999999">
      </div>
      <div class="auth-modal-field">
        <label class="auth-modal-label" for="auth-register-password">{% trans "Парола" %}</label>
        <input type="password" id="auth-register-password" class="auth-modal-input" autocomplete="new-password">
      </div>
      <div class="auth-modal-field">
        <label class="auth-modal-label" for="auth-register-dob">{% trans "Дата на раждане (незадължително)" %}</label>
        <input type="date" id="auth-register-dob" class="auth-modal-input">
      </div>
      <div class="auth-modal-honeypot" aria-hidden="true">
        <label for="auth-register-middle-name">{% trans "Презиме" %}</label>
        <input type="text" id="auth-register-middle-name" tabindex="-1" autocomplete="off">
      </div>
      <p class="auth-modal-error" id="auth-register-error"></p>
      <button type="button" class="btn btn-primary auth-modal-submit" id="auth-register-submit">{% trans "Регистрация" %}</button>
    </div>

  </div>
</div>

<script>
(function () {
    var overlay = document.getElementById('auth-modal');
    if (!overlay) return;

    var steps = {};
    Array.prototype.forEach.call(overlay.querySelectorAll('.auth-modal-step'), function (el) {
        steps[el.dataset.step] = el;
    });

    var closeBtn = document.getElementById('auth-modal-close');
    var emailInput = document.getElementById('auth-email-input');
    var emailError = document.getElementById('auth-email-error');
    var emailContinueBtn = document.getElementById('auth-email-continue');

    var choiceEmailLabel = document.getElementById('auth-choice-email');
    var choicePasswordBtn = document.getElementById('auth-choice-password');
    var choiceCodeBtn = document.getElementById('auth-choice-code');

    var passwordEmailLabel = document.getElementById('auth-password-email');
    var passwordInput = document.getElementById('auth-password-input');
    var passwordError = document.getElementById('auth-password-error');
    var passwordContinueBtn = document.getElementById('auth-password-continue');

    var codeSentTo = document.getElementById('auth-code-sent-to');
    var codeDigits = Array.prototype.slice.call(document.querySelectorAll('.auth-modal-code-digit'));
    var codeError = document.getElementById('auth-code-error');
    var codeContinueBtn = document.getElementById('auth-code-continue');
    var codeResendBtn = document.getElementById('auth-code-resend');

    var registerFirstName = document.getElementById('auth-register-first-name');
    var registerLastName = document.getElementById('auth-register-last-name');
    var registerPhone = document.getElementById('auth-register-phone');
    var registerPassword = document.getElementById('auth-register-password');
    var registerDob = document.getElementById('auth-register-dob');
    var registerMiddleName = document.getElementById('auth-register-middle-name');
    var registerError = document.getElementById('auth-register-error');
    var registerSubmitBtn = document.getElementById('auth-register-submit');

    var state = { email: '', next: '' };
    var turnstileToken = '';

    window.authModalTurnstileCallback = function (token) { turnstileToken = token; };

    function resetTurnstile() {
        turnstileToken = '';
        if (window.turnstile && document.getElementById('auth-turnstile')) {
            window.turnstile.reset('#auth-turnstile');
        }
    }

    function getCsrf() {
        var el = overlay.querySelector('[name=csrfmiddlewaretoken]');
        return el ? el.value : '';
    }

    function showStep(name) {
        Object.keys(steps).forEach(function (key) { steps[key].hidden = key !== name; });
    }

    function post(url, fields) {
        var fd = new FormData();
        fd.append('csrfmiddlewaretoken', getCsrf());
        Object.keys(fields).forEach(function (key) { fd.append(key, fields[key]); });
        return fetch(url, { method: 'POST', body: fd }).then(function (r) {
            return r.json().then(function (data) { return { ok: r.ok, data: data }; });
        });
    }

    function getCode() {
        return codeDigits.map(function (d) { return d.value; }).join('');
    }

    function finishAuth(redirect) {
        window.location.href = redirect || state.next || '/';
    }

    function open(opts) {
        opts = opts || {};
        state.next = opts.next || '';
        state.email = '';
        emailInput.value = '';
        emailError.textContent = '';
        codeDigits.forEach(function (d) { d.value = ''; });
        showStep('email');
        overlay.classList.add('open');
        overlay.setAttribute('aria-hidden', 'false');
        resetTurnstile();
        setTimeout(function () { emailInput.focus(); }, 50);
    }

    function close() {
        overlay.classList.remove('open');
        overlay.setAttribute('aria-hidden', 'true');
    }

    closeBtn.addEventListener('click', close);
    overlay.addEventListener('click', function (e) { if (e.target === overlay) close(); });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && overlay.classList.contains('open')) close();
    });

    codeDigits.forEach(function (input, index) {
        input.addEventListener('input', function () {
            input.value = input.value.replace(/\D/g, '').slice(0, 1);
            if (input.value && codeDigits[index + 1]) codeDigits[index + 1].focus();
        });
        input.addEventListener('keydown', function (e) {
            if (e.key === 'Backspace' && !input.value && codeDigits[index - 1]) codeDigits[index - 1].focus();
        });
    });

    function requestCode() {
        codeError.textContent = '';
        codeSentTo.textContent = state.email;
        showStep('code');
        return post('{% url "auth_send_code" %}', { email: state.email, turnstile_token: turnstileToken }).then(function (res) {
            resetTurnstile();
            if (!res.data.success) { codeError.textContent = res.data.error || ''; }
        }).catch(function () {
            resetTurnstile();
            codeError.textContent = '{{ msg_generic_error|escapejs }}';
        });
    }

    emailContinueBtn.addEventListener('click', function () {
        var email = emailInput.value.trim();
        emailError.textContent = '';
        if (!email) { emailError.textContent = '{{ msg_enter_email|escapejs }}'; return; }

        state.email = email;
        emailContinueBtn.disabled = true;

        post('{% url "auth_check_email" %}', { email: email }).then(function (res) {
            emailContinueBtn.disabled = false;
            if (!res.data.success) { emailError.textContent = res.data.error || ''; return; }

            if (res.data.exists) {
                choiceEmailLabel.textContent = email;
                passwordEmailLabel.textContent = email;
                showStep('choice');
            } else {
                requestCode();
            }
        }).catch(function () {
            emailContinueBtn.disabled = false;
            emailError.textContent = '{{ msg_generic_error|escapejs }}';
        });
    });

    choicePasswordBtn.addEventListener('click', function () {
        passwordInput.value = '';
        passwordError.textContent = '';
        showStep('password');
    });

    choiceCodeBtn.addEventListener('click', function () { requestCode(); });
    codeResendBtn.addEventListener('click', function () { requestCode(); });

    passwordContinueBtn.addEventListener('click', function () {
        passwordError.textContent = '';
        passwordContinueBtn.disabled = true;
        post('{% url "auth_login_password" %}', {
            email: state.email, password: passwordInput.value, next: state.next,
        }).then(function (res) {
            passwordContinueBtn.disabled = false;
            if (res.data.success) { finishAuth(res.data.redirect); }
            else { passwordError.textContent = res.data.error || ''; }
        }).catch(function () {
            passwordContinueBtn.disabled = false;
            passwordError.textContent = '{{ msg_generic_error|escapejs }}';
        });
    });

    codeContinueBtn.addEventListener('click', function () {
        var code = getCode();
        codeError.textContent = '';
        if (code.length !== 6) { codeError.textContent = '{{ msg_enter_all_digits|escapejs }}'; return; }

        codeContinueBtn.disabled = true;
        post('{% url "auth_verify_code" %}', { email: state.email, code: code, next: state.next }).then(function (res) {
            codeContinueBtn.disabled = false;
            if (!res.data.success) { codeError.textContent = res.data.error || ''; return; }

            if (res.data.status === 'logged_in') { finishAuth(res.data.redirect); return; }

            if (res.data.status === 'verified') {
                registerFirstName.value = '';
                registerLastName.value = '';
                registerPhone.value = '';
                registerPassword.value = '';
                registerDob.value = '';
                registerMiddleName.value = '';
                registerError.textContent = '';
                showStep('register');
            }
        }).catch(function () {
            codeContinueBtn.disabled = false;
            codeError.textContent = '{{ msg_generic_error|escapejs }}';
        });
    });

    registerSubmitBtn.addEventListener('click', function () {
        registerError.textContent = '';
        registerSubmitBtn.disabled = true;
        post('{% url "auth_register" %}', {
            first_name: registerFirstName.value,
            last_name: registerLastName.value,
            phone_number: registerPhone.value,
            password: registerPassword.value,
            date_of_birth: registerDob.value,
            middle_name: registerMiddleName.value,
            turnstile_token: turnstileToken,
            next: state.next,
        }).then(function (res) {
            registerSubmitBtn.disabled = false;
            resetTurnstile();
            if (res.data.success) { finishAuth(res.data.redirect); return; }
            if (res.data.errors) {
                var firstField = Object.keys(res.data.errors)[0];
                registerError.textContent = firstField ? res.data.errors[firstField][0] : (res.data.error || '');
            } else {
                registerError.textContent = res.data.error || '';
            }
        }).catch(function () {
            registerSubmitBtn.disabled = false;
            resetTurnstile();
            registerError.textContent = '{{ msg_generic_error|escapejs }}';
        });
    });

    window.AuthModal = { open: open, close: close };
})();
</script>
```

- [ ] **Step 3: Add the CSS**

Create `staticfiles/css/components/auth-modal.css`:
```css
/* ================================================================
   AUTH MODAL — shared login/signup modal (booking + header entry)
   ================================================================ */
.auth-modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.45);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1100;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.25s ease;
    padding: 1rem;
}

.auth-modal-overlay.open {
    opacity: 1;
    pointer-events: auto;
}

.auth-modal {
    position: relative;
    background: #fff;
    border-radius: 16px;
    padding: 2.5rem;
    max-width: 420px;
    width: 100%;
    box-shadow: 0 20px 60px rgba(74, 55, 40, 0.15);
}

.auth-modal-close {
    position: absolute;
    top: 1rem;
    right: 1.25rem;
    background: none;
    border: none;
    font-size: 1.5rem;
    line-height: 1;
    color: var(--text-muted);
    cursor: pointer;
    padding: 0;
}

.auth-modal-close:hover { color: var(--primary-color); }

.auth-modal-title {
    font-family: var(--font-heading);
    font-size: 1.4rem;
    font-weight: 600;
    color: var(--primary-color);
    margin: 0 0 0.5rem;
}

.auth-modal-subtitle {
    font-size: 0.9rem;
    color: var(--text-muted);
    margin: 0 0 1.5rem;
}

.auth-modal-step[hidden] { display: none; }

.auth-modal-field { margin-bottom: 1.25rem; }

.auth-modal-label {
    display: block;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 0.5rem;
}

.auth-modal-input {
    width: 100%;
    padding: 0.75rem 1rem;
    border: 1.5px solid var(--hp-border);
    border-radius: 8px;
    font-size: 1rem;
    font-family: var(--font-main);
    color: var(--text-main);
    background: #fff;
    box-sizing: border-box;
    transition: border-color 0.2s;
    outline: none;
}

.auth-modal-input:focus { border-color: var(--accent-color); }

.auth-modal-error {
    color: #B3261E;
    font-size: 0.85rem;
    margin: -0.5rem 0 1rem;
    min-height: 1.2em;
}

.auth-modal-error:empty { display: none; }

.auth-modal-submit { width: 100%; margin-bottom: 0.75rem; }

.auth-modal-footnote {
    text-align: center;
    font-size: 0.85rem;
    color: var(--text-muted);
    margin-top: 1rem;
}

.auth-modal-link-btn {
    background: none;
    border: none;
    padding: 0;
    color: var(--accent-color);
    cursor: pointer;
    font-size: inherit;
    text-decoration: underline;
}

.auth-modal-code-inputs {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
}

.auth-modal-code-digit {
    width: 100%;
    aspect-ratio: 1 / 1;
    text-align: center;
    font-size: 1.25rem;
    border: 1.5px solid var(--hp-border);
    border-radius: 8px;
    outline: none;
}

.auth-modal-code-digit:focus { border-color: var(--accent-color); }

/* Honeypot: off-screen, unreachable by sighted or keyboard users, but
   present in the DOM for bots that scrape and auto-fill form fields. */
.auth-modal-honeypot {
    position: absolute;
    left: -9999px;
    width: 1px;
    height: 1px;
    overflow: hidden;
}
```

In `staticfiles/css/styles.css`, add under the "Components styles" section:
```css
@import url('components/auth-modal.css');
```

- [ ] **Step 4: Verify no template/syntax errors**

Run: `python manage.py check`
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 5: Commit**

```bash
git add massageProject/massageProject/accounts/context_processors.py massageProject/massageProject/settings.py templates/partials/auth_modal.html staticfiles/css/components/auth-modal.css staticfiles/css/styles.css
git commit -m "feat: add auth modal partial with CSS and step-flow JS"
```

---

### Task 11: Wire the modal into `base.html` and intercept "Book Now"/header links

**Files:**
- Modify: `templates/base.html`
- Modify: `templates/partials/header.html`
- Modify: `templates/partials/featured_with_image.html`
- Modify: `templates/pages/home.html`
- Modify: `templates/pages/massage_detail.html`
- Modify: `templates/pages/my_profile.html`
- Modify: `templates/pages/massages_page.html`

**Interfaces:**
- Consumes: `window.AuthModal.open({next})` (Task 10).
- Produces: `window.IS_AUTHENTICATED` global flag; `data-auth-modal-link` / `data-auth-modal-trigger` attribute convention used by any future "Book Now"-style link.

- [ ] **Step 1: Include the modal and Turnstile script in `base.html`**

In `templates/base.html`, replace:
```html
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Massage Center</title>
    <link rel="stylesheet" href="{% static 'css/styles.css' %}">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css" rel="stylesheet">
</head>
<body>
    {% include 'partials/header.html' %}
```
with:
```html
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Massage Center</title>
    <link rel="stylesheet" href="{% static 'css/styles.css' %}">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css" rel="stylesheet">
    <script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
</head>
<body>
    <script>window.IS_AUTHENTICATED = {{ user.is_authenticated|yesno:"true,false" }};</script>
    {% include 'partials/header.html' %}
```
And replace:
```html
    {% include 'partials/footer.html' %}

    <script src="{% static 'js/resposive_menu_button.js' %}"></script>
</body>
```
with:
```html
    {% include 'partials/footer.html' %}
    {% include 'partials/auth_modal.html' %}

    <script src="{% static 'js/resposive_menu_button.js' %}"></script>
</body>
```

- [ ] **Step 2: Add the click-intercept script and mark up the header's own links**

In `templates/partials/header.html`, replace the CTA anchor:
```html
        <a href="{% url 'reservation_page' %}" class="btn btn-primary navbar-cta" title="{% trans 'Запазете час' %}">
```
with:
```html
        <a href="{% url 'reservation_page' %}" class="btn btn-primary navbar-cta" data-auth-modal-link title="{% trans 'Запазете час' %}">
```

Replace the mobile auth links block:
```html
            {% else %}
                <a href="{% url 'login' %}">{% trans "Вход" %}</a>
                <a href="{% url 'register' %}">{% trans "Регистрация" %}</a>
            {% endif %}
```
with:
```html
            {% else %}
                <a href="#" data-auth-modal-trigger>{% trans "Вход" %}</a>
                <a href="#" data-auth-modal-trigger>{% trans "Регистрация" %}</a>
            {% endif %}
```

Replace the desktop dropdown auth links block:
```html
                {% else %}
                    <a href="{% url 'login' %}" role="menuitem">{% trans "Вход" %}</a>
                    <a href="{% url 'register' %}" role="menuitem">{% trans "Регистрация" %}</a>
                {% endif %}
```
with:
```html
                {% else %}
                    <a href="#" role="menuitem" data-auth-modal-trigger>{% trans "Вход" %}</a>
                    <a href="#" role="menuitem" data-auth-modal-trigger>{% trans "Регистрация" %}</a>
                {% endif %}
```

Append a second `<script>` tag at the end of `templates/partials/header.html` (after the existing one):
```html
<script>
document.addEventListener('DOMContentLoaded', function () {
    function openAuthModal(next) {
        if (window.AuthModal) { window.AuthModal.open({ next: next }); }
    }

    document.querySelectorAll('[data-auth-modal-link]').forEach(function (link) {
        link.addEventListener('click', function (e) {
            if (window.IS_AUTHENTICATED) return;
            e.preventDefault();
            openAuthModal(link.getAttribute('href'));
        });
    });

    document.querySelectorAll('[data-auth-modal-trigger]').forEach(function (link) {
        link.addEventListener('click', function (e) {
            e.preventDefault();
            openAuthModal('{% url "reservation_page" %}');
        });
    });
});
</script>
```

- [ ] **Step 3: Mark up the remaining "Book Now" links**

In `templates/partials/featured_with_image.html`, replace:
```html
            <a href="{% url 'reservation_page' %}?massage={{ m.pk }}" class="btn btn-primary hp-feat-book">{% trans "Запазете час" %}</a>
```
with:
```html
            <a href="{% url 'reservation_page' %}?massage={{ m.pk }}" class="btn btn-primary hp-feat-book" data-auth-modal-link>{% trans "Запазете час" %}</a>
```

In `templates/pages/home.html`, replace (line 15):
```html
                <a href="{% url 'reservation_page' %}" class="btn btn-primary btn-lg">{% trans "Запазете час" %}</a>
```
with:
```html
                <a href="{% url 'reservation_page' %}" class="btn btn-primary btn-lg" data-auth-modal-link>{% trans "Запазете час" %}</a>
```
And replace (line 203):
```html
                <a href="{% url 'reservation_page' %}" class="btn btn-primary btn-block">{% trans "Запазете час" %}</a>
```
with:
```html
                <a href="{% url 'reservation_page' %}" class="btn btn-primary btn-block" data-auth-modal-link>{% trans "Запазете час" %}</a>
```

In `templates/pages/massage_detail.html`, replace:
```html
        <a href="{% url 'reservation_page' pk=massage.pk %}" class="btn">{% trans "Направи резервация" %}</a>
```
with:
```html
        <a href="{% url 'reservation_page' pk=massage.pk %}" class="btn" data-auth-modal-link>{% trans "Направи резервация" %}</a>
```

In `templates/pages/my_profile.html`, replace (line 104):
```html
        <a href="{% url 'reservation_page' %}" class="btn-primary-profile">+ {% trans "Запазете нов час" %}</a>
```
with:
```html
        <a href="{% url 'reservation_page' %}" class="btn-primary-profile" data-auth-modal-link>+ {% trans "Запазете нов час" %}</a>
```
And replace (lines 187-189):
```html
            <a href="{% url 'reservation_page' %}?massage={{ r.massage.pk }}" class="btn-outline-sm">
              &rarr; {% trans "Запазете отново" %}
            </a>
```
with:
```html
            <a href="{% url 'reservation_page' %}?massage={{ r.massage.pk }}" class="btn-outline-sm" data-auth-modal-link>
              &rarr; {% trans "Запазете отново" %}
            </a>
```

In `templates/pages/massages_page.html`, replace:
```html
              <a href="{% url 'reservation_page' %}" class="svc-btn svc-btn--primary">{% trans "Резервирай" %}</a>
```
with:
```html
              <a href="{% url 'reservation_page' %}" class="svc-btn svc-btn--primary" data-auth-modal-link>{% trans "Резервирай" %}</a>
```

Note: on `my_profile.html` and `massage_detail.html`/etc. these pages are normally only linked to for already-authenticated users in practice, but the intercept is harmless either way since it checks `window.IS_AUTHENTICATED` and does nothing for already-logged-in users (link navigates normally).

- [ ] **Step 4: Verify no template errors**

Run: `python manage.py check`
Expected: `System check identified no issues (0 silenced).`

Run the full existing suite to confirm nothing broke:
Run: `python manage.py test massageProject.main_app.tests massageProject.accounts.tests`
Expected: `OK` (these are the pre-existing single-module test files; the many `tests_*.py` files run automatically too when you run `python manage.py test massageProject.accounts massageProject.main_app` — use that broader form here)

Run: `python manage.py test massageProject.accounts massageProject.main_app`
Expected: `OK`, all tests pass (no template referencing `{% url 'login' %}`/`{% url 'register' %}` was touched in a way that breaks reversal — both names still exist until Task 12).

- [ ] **Step 5: Commit**

```bash
git add templates/base.html templates/partials/header.html templates/partials/featured_with_image.html templates/pages/home.html templates/pages/massage_detail.html templates/pages/my_profile.html templates/pages/massages_page.html
git commit -m "feat: intercept Book Now and header login/register links to open the auth modal"
```

---

### Task 12: Remove the old registration/login/verification flow

This is the big cleanup task: it deletes everything superseded by Tasks 4-11, and adds `AuthEntryView` so the `login` URL name (Django's default `LOGIN_URL`, used by `ProfilePage`/`edit_reservation`/`delete_reservation`'s `LoginRequiredMixin`/`@login_required`) still resolves to something — now the same auth modal, auto-opened.

**Files:**
- Modify: `massageProject/massageProject/accounts/views.py`
- Modify: `massageProject/massageProject/accounts/urls.py`
- Modify: `massageProject/massageProject/accounts/forms.py`
- Modify: `massageProject/massageProject/accounts/emails.py`
- Delete: `massageProject/massageProject/accounts/tokens.py`
- Create: `templates/registration/auth_entry.html`
- Delete: `templates/registration/login.html`
- Delete: `templates/registration/register.html`
- Delete: `templates/registration/verification_sent.html`
- Delete: `templates/registration/resend_verification.html`
- Modify: `templates/pages/reservation.html`
- Delete: `massageProject/massageProject/accounts/tests.py`
- Delete: `massageProject/massageProject/accounts/tests_registration.py`
- Delete: `massageProject/massageProject/accounts/tests_resend_verification.py`
- Delete: `massageProject/massageProject/accounts/tests_tokens.py`
- Delete: `massageProject/massageProject/accounts/tests_emails.py`
- Modify: `massageProject/massageProject/accounts/tests_inactive_login.py`

**Interfaces:**
- Produces: `AuthEntryView` (view class in `views.py`), URL name `login` now points to it.
- Consumes: `window.AuthModal.open({next})` from `templates/partials/auth_modal.html` (Task 10), which is included in `base.html` (Task 11) — so `AuthEntryView`'s template can call it.

- [ ] **Step 1: Add `AuthEntryView` and its template**

In `massageProject/massageProject/accounts/views.py`, replace the entire file contents with (this removes `UserRegisterView`, `VerifyEmailView`, `ResendVerificationView` and adds `AuthEntryView`; `BrandedPasswordResetView` is carried over unchanged from its current form):
```python
from django.contrib.auth.views import PasswordResetView
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView


class AuthEntryView(TemplateView):
    """
    Fallback destination for the 'login' URL name -- Django's default
    LOGIN_URL. LoginRequiredMixin/@login_required (ProfilePage,
    edit_reservation, delete_reservation) redirect anonymous users here.
    Instead of a full login page, this renders the site shell and
    auto-opens the shared auth modal (partials/auth_modal.html), passing
    along ?next= so the modal knows where to send the user afterward.
    """
    template_name = 'registration/auth_entry.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['next'] = self.request.GET.get('next', '')
        return context


class BrandedPasswordResetView(PasswordResetView):
    template_name = 'registration/password_reset_form.html'
    email_template_name = 'emails/password_reset_email.txt'
    html_email_template_name = 'emails/password_reset_email.html'
    subject_template_name = 'emails/password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')

    @property
    def extra_email_context(self):
        from massageProject.main_app.models import HomePage, MessageStudio

        homepage = HomePage.get_solo()
        studio = MessageStudio.objects.first()
        logo_url = None
        if homepage and homepage.logo:
            logo_url = self.request.build_absolute_uri(homepage.logo.url)

        return {
            'brand_name': homepage.brand_name if homepage else _('Relax & Health'),
            'studio': studio,
            'logo_url': logo_url,
        }
```

Create `templates/registration/auth_entry.html`:
```html
{% extends 'base.html' %}
{% load i18n %}
{% block content %}
<noscript><p>{% trans "Моля, включете JavaScript, за да влезете в профила си." %}</p></noscript>
<script>
document.addEventListener('DOMContentLoaded', function () {
    if (window.AuthModal) {
        window.AuthModal.open({ next: "{{ next|escapejs }}" });
    }
});
</script>
{% endblock %}
```

- [ ] **Step 2: Repoint `login`, remove the old URLs**

Replace `massageProject/massageProject/accounts/urls.py` entirely with:
```python
from django.urls import path, reverse_lazy
from django.contrib.auth.views import (
    LogoutView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView,
)

from massageProject.accounts.views import AuthEntryView, BrandedPasswordResetView
from massageProject.accounts.booking_auth_views import (
    check_email, send_code, verify_code, register_via_modal, login_password,
)

urlpatterns = [
    path('login/', AuthEntryView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),

    path('auth-modal/check-email/', check_email, name='auth_check_email'),
    path('auth-modal/send-code/', send_code, name='auth_send_code'),
    path('auth-modal/verify-code/', verify_code, name='auth_verify_code'),
    path('auth-modal/login-password/', login_password, name='auth_login_password'),
    path('auth-modal/register/', register_via_modal, name='auth_register'),

    path('password-reset/', BrandedPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html'
    ), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html',
        success_url=reverse_lazy('password_reset_complete'),
    ), name='password_reset_confirm'),
    path('reset/done/', PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html'
    ), name='password_reset_complete'),
]
```

- [ ] **Step 3: Remove `CustomUserForm`/`ResendVerificationForm`, `tokens.py`, and `send_verification_email`**

In `massageProject/massageProject/accounts/forms.py`, delete the `CustomUserForm` class and the `ResendVerificationForm` class entirely (everything from `class CustomUserForm(UserCreationForm):` through the end of `class ResendVerificationForm(forms.Form):`). Keep `CustomAuthenticationForm`, `PhoneClaimFormMixin`, and `BookingRegistrationForm`. The `UserCreationForm` import becomes unused — remove it from the top import line, leaving:
```python
from django.contrib.auth.forms import AuthenticationForm
```

Delete `massageProject/massageProject/accounts/tokens.py`.

In `massageProject/massageProject/accounts/emails.py`, delete the `send_verification_email` function and its now-unused imports (`reverse`, `force_bytes`, `urlsafe_base64_encode`, and the `email_verification_token_generator` import), leaving only:
```python
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _


def send_otp_email(request, email, code):
    from massageProject.main_app.models import HomePage

    homepage = HomePage.get_solo()
    logo_url = None
    if homepage and homepage.logo:
        logo_url = request.build_absolute_uri(homepage.logo.url)

    context = {
        'code': code,
        'brand_name': homepage.brand_name if homepage else _('Relax & Health'),
        'logo_url': logo_url,
    }
    subject = render_to_string('emails/otp_email_subject.txt', context).strip()
    text_body = render_to_string('emails/otp_email.txt', context)
    html_body = render_to_string('emails/otp_email.html', context)

    message = EmailMultiAlternatives(subject, text_body, settings.DEFAULT_FROM_EMAIL, [email])
    message.attach_alternative(html_body, 'text/html')
    message.send()
```

- [ ] **Step 4: Delete the superseded templates, edit `reservation.html`, delete obsolete tests**

Delete:
```bash
git rm templates/registration/login.html templates/registration/register.html templates/registration/verification_sent.html templates/registration/resend_verification.html
```

In `templates/pages/reservation.html`, replace:
```html
{% block content %}

{% if not user.is_authenticated %}

<section class="bn-unauth">
  <h2>{% trans "Запазете час" %}</h2>
  <p>{% trans "За да направите резервация, моля" %} <a href="{% url 'register' %}">{% trans "регистрирайте се" %}</a> {% trans "или" %} <a href="{% url 'login' %}">{% trans "влезте" %}</a>.</p>
</section>

{% else %}

<div class="book-page">
```
with:
```html
{% block content %}

<div class="book-page">
```
And replace (at the very end of the file):
```html
</script>

{% endif %}
{% endblock %}
```
with:
```html
</script>

{% endblock %}
```

Delete the now-obsolete test files:
```bash
git rm massageProject/massageProject/accounts/tests.py massageProject/massageProject/accounts/tests_registration.py massageProject/massageProject/accounts/tests_resend_verification.py massageProject/massageProject/accounts/tests_tokens.py massageProject/massageProject/accounts/tests_emails.py
```

In `massageProject/massageProject/accounts/tests_inactive_login.py`, remove the four tests that POST to `reverse('login')` (`test_inactive_user_correct_password_sees_custom_inactive_message`, `test_inactive_user_correct_password_sees_message_in_rendered_html`, `test_active_user_correct_password_logs_in`, `test_active_user_wrong_password_sees_generic_message_not_inactive_message`, `test_inactive_user_wrong_password_sees_generic_message_not_inactive_message` — five methods; the `login-password/` equivalents already exist in `tests_login_password_view.py` from Task 9). Keep only `_create_user` and `test_deactivating_a_logged_in_user_invalidates_their_session`, and update the class docstring. The final file:
```python
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class InactiveUserLoginTest(TestCase):
    """
    Regression test: deactivating a logged-in user must invalidate their
    existing session on their very next request. The credential-flow
    variants of this test class (inactive user + correct/wrong password via
    the login view) moved to tests_login_password_view.py when the
    full-page login view was replaced by the auth modal's login-password/
    endpoint.
    """

    PASSWORD = 'ComplexPass!123'

    def _create_user(self, email, phone_number, is_active):
        user = User.objects.create_user(
            email=email,
            phone_number=phone_number,
            password=self.PASSWORD,
        )
        user.is_active = is_active
        user.save(update_fields=['is_active'])
        return user

    def test_deactivating_a_logged_in_user_invalidates_their_session(self):
        user = self._create_user('deactivateme@example.com', '0888666666', is_active=True)

        logged_in = self.client.login(
            username='deactivateme@example.com', password=self.PASSWORD,
        )
        self.assertTrue(logged_in)

        response = self.client.get(reverse('profile_page'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.wsgi_request.user.is_authenticated)

        user.is_active = False
        user.save(update_fields=['is_active'])

        response = self.client.get(reverse('profile_page'))
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
```

- [ ] **Step 5: Run the full suite, then commit**

Run: `python manage.py test massageProject.accounts massageProject.main_app`
Expected: `OK`, no failures, no `ImportError`/`NoReverseMatch`.

Run: `python manage.py check`
Expected: `System check identified no issues (0 silenced).`

```bash
git add -A massageProject/massageProject/accounts templates/registration templates/pages/reservation.html
git commit -m "refactor: remove the old link-based login/register/verification flow"
```

---

### Task 13: Translations (bg/en)

**Files:**
- Modify: `locale/bg/LC_MESSAGES/django.po`
- Modify: `locale/en/LC_MESSAGES/django.po`
- Modify (compiled, binary): `locale/bg/LC_MESSAGES/django.mo`, `locale/en/LC_MESSAGES/django.mo`

**Interfaces:** None — this task only adds translations for strings already introduced in Tasks 1-12.

- [ ] **Step 1: Extract new msgids**

```bash
source venv/bin/activate
python manage.py makemessages -l bg -l en
```
Expected: `locale/bg/LC_MESSAGES/django.po` and `locale/en/LC_MESSAGES/django.po` gain new `msgid` entries for every new `{% trans %}`/`_()` string introduced across Tasks 1-12 (e.g. "Влезте или се регистрирайте", "Как искате да влезете?", "С парола", "С код по имейл", "Потвърдете своя имейл", "Не получихте код?", "Изпрати отново", "Създайте профил", "Презиме", "Твърде много опити. Опитайте отново по-късно.", "Проверката за робот не е успешна. Опитайте отново.", "Кодът е грешен или е изтекъл.", "Няма активен код за този имейл. Изпратете нов.", "Имейлът не е потвърден или потвърждението е изтекло.", "Ваш код за потвърждение", "Дата на раждане (незадължително)", "date of birth", "Signup", "Login", "Затвори", "Моля, включете JavaScript, за да влезете в профила си.", etc.)

- [ ] **Step 2: Fill in translations**

Open `locale/bg/LC_MESSAGES/django.po`: since the source strings are already Bulgarian, set each new entry's `msgstr` to the same text as its `msgid` (matching the existing pattern for other bg entries in the file, which mostly mirror the source).

Open `locale/en/LC_MESSAGES/django.po`: translate each new `msgid` to English, e.g.:
```
msgid "Влезте или се регистрирайте"
msgstr "Log in or sign up"

msgid "Как искате да влезете?"
msgstr "How would you like to log in?"

msgid "С парола"
msgstr "With a password"

msgid "С код по имейл"
msgstr "With an emailed code"

msgid "Потвърдете своя имейл"
msgstr "Confirm your email"

msgid "Не получихте код?"
msgstr "Didn't receive a code?"

msgid "Изпрати отново"
msgstr "Resend"

msgid "Създайте профил"
msgstr "Create your account"

msgid "Презиме"
msgstr "Middle name"

msgid "Твърде много опити. Опитайте отново по-късно."
msgstr "Too many attempts. Please try again later."

msgid "Проверката за робот не е успешна. Опитайте отново."
msgstr "The bot check failed. Please try again."

msgid "Кодът е грешен или е изтекъл."
msgstr "The code is incorrect or has expired."

msgid "Няма активен код за този имейл. Изпратете нов."
msgstr "There is no active code for this email. Send a new one."

msgid "Имейлът не е потвърден или потвърждението е изтекло."
msgstr "The email hasn't been verified, or verification has expired."

msgid "Ваш код за потвърждение"
msgstr "Your verification code"

msgid "Дата на раждане (незадължително)"
msgstr "Date of birth (optional)"

msgid "date of birth"
msgstr "date of birth"

msgid "Затвори"
msgstr "Close"

msgid "Моля, включете JavaScript, за да влезете в профила си."
msgstr "Please enable JavaScript to log in."
```
(The exact list of new msgids depends on `makemessages`' output — translate every new entry it added; the strings above cover everything introduced by this plan's tasks.)

- [ ] **Step 3: Compile**

```bash
python manage.py compilemessages
```
Expected: `processing file django.po in .../locale/bg/LC_MESSAGES` and the same for `en`, no errors.

- [ ] **Step 4: Verify no msgid is left untranslated in English**

Run: `grep -B1 'msgstr ""$' locale/en/LC_MESSAGES/django.po | grep -A1 -E "auth-modal|Затвори|код|парола|Регистрация|Твърде|робот" `
Expected: no output (i.e. none of this plan's new strings are still empty in the English file). Any hits mean a translation was missed — go back to Step 2.

- [ ] **Step 5: Commit**

```bash
git add locale/bg/LC_MESSAGES/django.po locale/bg/LC_MESSAGES/django.mo locale/en/LC_MESSAGES/django.po locale/en/LC_MESSAGES/django.mo
git commit -m "i18n: translate new booking auth modal strings (bg/en)"
```

---

### Task 14: End-to-end integration tests

**Files:**
- Create: `massageProject/massageProject/accounts/tests_auth_modal_e2e.py`

**Interfaces:** None new — exercises everything from Tasks 4-9 together via the Django test client.

- [ ] **Step 1: Write the end-to-end tests**

Create `massageProject/massageProject/accounts/tests_auth_modal_e2e.py`:
```python
import re
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

User = get_user_model()

TURNSTILE_PATCH = 'massageProject.accounts.booking_auth_views.verify_turnstile_token'


def _extract_code(email_body):
    match = re.search(r'\b(\d{6})\b', email_body)
    assert match, 'no 6-digit code found in email body'
    return match.group(1)


class NewUserBookingAuthFlowTest(TestCase):
    def setUp(self):
        cache.clear()

    @patch(TURNSTILE_PATCH, return_value=True)
    def test_full_signup_round_trip(self, mock_turnstile):
        email = 'brandnew@example.com'

        check_resp = self.client.post(reverse('auth_check_email'), {'email': email})
        self.assertFalse(check_resp.json()['exists'])

        send_resp = self.client.post(reverse('auth_send_code'), {
            'email': email, 'turnstile_token': 'ok',
        })
        self.assertTrue(send_resp.json()['success'])
        self.assertEqual(len(mail.outbox), 1)

        code = _extract_code(mail.outbox[0].body)

        verify_resp = self.client.post(reverse('auth_verify_code'), {'email': email, 'code': code})
        verify_data = verify_resp.json()
        self.assertTrue(verify_data['success'])
        self.assertEqual(verify_data['status'], 'verified')

        register_resp = self.client.post(reverse('auth_register'), {
            'first_name': 'Nova', 'last_name': 'User',
            'phone_number': '0888950001', 'password': 'ComplexPass!123',
            'turnstile_token': 'ok',
        })
        register_data = register_resp.json()
        self.assertTrue(register_data['success'])
        self.assertEqual(register_data['status'], 'registered')

        user = User.objects.get(email=email)
        self.assertTrue(user.is_active)

        profile_resp = self.client.get(reverse('profile_page'))
        self.assertTrue(profile_resp.wsgi_request.user.is_authenticated)
        self.assertEqual(profile_resp.wsgi_request.user.pk, user.pk)


class ExistingUserBookingAuthFlowTest(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email='returning@example.com', phone_number='0888950002', password='ComplexPass!123',
        )

    def test_existing_user_logs_in_with_password(self):
        check_resp = self.client.post(reverse('auth_check_email'), {'email': 'returning@example.com'})
        self.assertTrue(check_resp.json()['exists'])

        login_resp = self.client.post(reverse('auth_login_password'), {
            'email': 'returning@example.com', 'password': 'ComplexPass!123',
        })
        data = login_resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['status'], 'logged_in')

        profile_resp = self.client.get(reverse('profile_page'))
        self.assertTrue(profile_resp.wsgi_request.user.is_authenticated)
        self.assertEqual(profile_resp.wsgi_request.user.pk, self.user.pk)

    @patch(TURNSTILE_PATCH, return_value=True)
    def test_existing_user_logs_in_with_emailed_code(self, mock_turnstile):
        send_resp = self.client.post(reverse('auth_send_code'), {
            'email': 'returning@example.com', 'turnstile_token': 'ok',
        })
        self.assertTrue(send_resp.json()['success'])
        code = _extract_code(mail.outbox[0].body)

        verify_resp = self.client.post(reverse('auth_verify_code'), {
            'email': 'returning@example.com', 'code': code,
        })
        data = verify_resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['status'], 'logged_in')

        profile_resp = self.client.get(reverse('profile_page'))
        self.assertTrue(profile_resp.wsgi_request.user.is_authenticated)
        self.assertEqual(profile_resp.wsgi_request.user.pk, self.user.pk)
```

- [ ] **Step 2: Run to verify it fails first (sanity check the harness), then implement is already done — just run for real**

Run: `python manage.py test massageProject.accounts.tests_auth_modal_e2e -v 2`
Expected: `OK` (3 tests) — all underlying endpoints already exist from Tasks 4-9, so this test file requires no new implementation code, only verifies the pieces work together. `_extract_code` pulls the 6-digit code out of the email body via regex, so it doesn't depend on `otp_email.txt`'s exact line layout.

- [ ] **Step 3: Commit**

```bash
git add massageProject/massageProject/accounts/tests_auth_modal_e2e.py
git commit -m "test: add end-to-end coverage for the new-user and existing-user auth modal flows"
```

---

### Task 15: Manual verification pass

No new files. This task is a checklist, run against the dev server, confirming the whole plan works together in a browser (automated tests cannot exercise the vanilla-JS modal or real Turnstile/Gmail integrations).

- [ ] **Step 1: Run the full automated suite one last time**

Run: `python manage.py test massageProject.accounts massageProject.main_app`
Expected: `OK`, zero failures.

- [ ] **Step 2: Set up local Turnstile testing keys**

In `.env`, set Cloudflare's published always-pass testing keys (safe for local dev only — replace with real keys before deploying):
```
TURNSTILE_SITE_KEY=1x00000000000000000000AA
TURNSTILE_SECRET_KEY=1x0000000000000000000000000000000AA
```

- [ ] **Step 3: Manually walk both flows in a browser**

```bash
python manage.py runserver
```
- Open the site logged out. Click "Book Now" in the header — the modal should open immediately (not the wizard).
- Enter a brand-new email → code step appears automatically → check the console/log for the sent email (or configure a real `EMAIL_HOST`) → enter the code → registration form appears → fill it in → submit → you land on `/reserve/` and are logged in.
- Log out. Click "Book Now" again with an email that now exists → the password-or-code choice step appears. Try "С код по имейл", confirm it logs you in. Try again with "С парола" and the correct password, confirm it logs you in.
- Try an intentionally wrong password — confirm the inline error appears without a page reload.
- Directly visit `/profile/` while logged out — confirm you land on the modal (via `AuthEntryView`) rather than a 404, and that after logging in you're redirected back to `/profile/`.

- [ ] **Step 4: Confirm this is the final step — no commit needed**

This task makes no code changes; it is a verification gate before considering the feature done. If any manual check fails, return to the relevant earlier task, fix it, and re-run its tests before continuing.

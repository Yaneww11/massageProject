# Google OAuth ("Continue with Google") Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Continue with Google" button to the auth modal (the site's single login/register entry point), wired through django-allauth, with a complete-profile step that collects the required phone number for new Google users.

**Architecture:** django-allauth is added for the *social* flow only — the existing email/OTP/password modal endpoints stay untouched. Full `allauth.urls` are included *after* the existing accounts urls (so the existing `login/` route wins), local allauth signup is closed via a custom account adapter, and a custom social adapter auto-links Google logins to existing accounts by email (existing users have no allauth `EmailAddress` rows, so allauth's built-in email-authentication setting would never match them). New Google users are forced through allauth's social signup view (`SOCIALACCOUNT_AUTO_SIGNUP = False`), which renders a branded complete-profile page collecting the required Bulgarian phone number.

**Tech Stack:** Django 6.0.6, django-allauth (>= 65.4, `socialaccount` extra) with the Google provider, django-environ for credentials, existing auth-modal CSS/JS.

## Decisions already made with the user (do not re-litigate)

1. New Google users go through a **complete-profile page** (phone required, names prefilled from Google and editable, date of birth optional, **no password field** — allauth sets an unusable password; users can later use email-code login or "Forgot password").
2. A Google login whose (Google-verified) email matches an existing account **auto-links and logs in** silently.
3. The button appears **only on the modal's email step**, under the email input, behind an "или"/"or" divider.
4. Credentials come from **env vars** `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET`; the user will create them in Google Cloud Console (instructions in Task 7).

## Global Constraints

- Django version: `Django==6.0.6` (already installed) — the allauth version installed must support Django 6.0.
- Virtualenv: run every command with the project venv active: `source venv/bin/activate` (or use `venv/bin/python` directly).
- All user-facing strings are written in **Bulgarian** wrapped in `{% trans %}` / `gettext_lazy` (Bulgarian is the msgid source language; `LANGUAGE_CODE = 'bg'`).
- URLs are language-prefixed via `i18n_patterns` with `prefix_default_language=True` — the OAuth callback lives at `/bg/accounts/google/login/callback/` and `/en/accounts/google/login/callback/`.
- Phone format: must satisfy the existing model validator regex `^(\+359|0)?8[789]\d{7}$` and be normalized via `User.objects.normalize_phone_number()` (`+359…` → `0…`).
- Existing modal JSON endpoints (`auth_check_email`, `auth_send_code`, `auth_verify_code`, `auth_register`, `auth_login_password`) must not change behavior.
- Existing url names `login`, `logout`, `password_reset*` must keep resolving to the existing views.
- Tests live in `massageProject/accounts/` as `tests_*.py` files (Django's `test*.py` discovery pattern) and run with `python manage.py test massageProject.accounts`.
- Commit message style (from git log): `feat:`, `test:`, `i18n:`, `docs:` prefixes, imperative mood.

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `requirements.txt` | modify | pin `django-allauth` |
| `massageProject/settings.py` | modify | allauth apps, middleware, backend, allauth settings, Google APP creds from env |
| `massageProject/accounts/urls.py` | modify | append `include('allauth.urls')` |
| `massageProject/accounts/adapters.py` | create | `ClosedSignupAccountAdapter` (no local allauth signup), `GoogleSocialAccountAdapter` (auto-link by email) |
| `massageProject/accounts/forms.py` | modify | add `SocialCompleteProfileForm` (phone required + claim logic, names prefilled, optional DOB) |
| `templates/socialaccount/signup.html` | create | branded complete-profile page |
| `templates/socialaccount/authentication_error.html` | create | branded OAuth error page |
| `templates/socialaccount/login_cancelled.html` | create | branded "cancelled at Google" page |
| `templates/account/inactive.html` | create | branded inactive-account page |
| `templates/partials/auth_modal.html` | modify | divider + Google button form + JS `next` propagation |
| `staticfiles/css/components/auth-modal.css` | modify | divider, Google button, standalone auth-page wrapper styles |
| `massageProject/accounts/tests_google_oauth.py` | create | all tests for this feature |
| `locale/bg/LC_MESSAGES/django.po`, `locale/en/LC_MESSAGES/django.po` | modify | new msgids + English translations |
| `README.md` | modify | Google Cloud Console setup instructions |

---

### Task 1: Install and wire django-allauth

**Files:**
- Modify: `requirements.txt`
- Modify: `massageProject/settings.py`
- Modify: `massageProject/accounts/urls.py`
- Test: `massageProject/accounts/tests_google_oauth.py` (create)

**Interfaces:**
- Consumes: nothing (first task).
- Produces: url names `google_login`, `google_callback`, `socialaccount_signup`, `account_signup`, `account_inactive` (all from `allauth.urls`); settings names `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET`; the `TEST_PROVIDERS` dict in the test file that every later test class reuses via `@override_settings(SOCIALACCOUNT_PROVIDERS=TEST_PROVIDERS)`.

- [ ] **Step 1: Install django-allauth and pin it**

```bash
source venv/bin/activate
pip install 'django-allauth[socialaccount]>=65.4'
pip show django-allauth | grep Version
```

Append the exact installed version to `requirements.txt`, keeping the file's alphabetical-ish grouping — add it right after the `Django==6.0.6` line, e.g. (replace `X.Y.Z` with the version `pip show` printed):

```
django-allauth==X.Y.Z
```

- [ ] **Step 2: Add allauth apps, middleware, backend, and settings**

In `massageProject/settings.py`, make these four edits.

Edit 1 — `INSTALLED_APPS` (insert after `'rosetta',`, before the two project apps):

```python
    'rosetta',

    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',

    'massageProject.accounts.apps.AccountsConfig',
    'massageProject.main_app.apps.MainAppConfig',
```

Edit 2 — `MIDDLEWARE` (append as the last entry):

```python
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]
```

Edit 3 — `AUTHENTICATION_BACKENDS` (allauth's backend performs the login after a social auth):

```python
AUTHENTICATION_BACKENDS = [
    'massageProject.accounts.backends.VerificationAwareBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]
```

Edit 4 — new settings block, placed directly after the `TURNSTILE_SECRET_KEY` line and before `# Unfold Configuration`:

```python
# django-allauth -- used ONLY for "Continue with Google"; the email/OTP/password
# flows stay on the custom booking auth modal endpoints.
GOOGLE_OAUTH_CLIENT_ID = env('GOOGLE_OAUTH_CLIENT_ID', default='')
GOOGLE_OAUTH_CLIENT_SECRET = env('GOOGLE_OAUTH_CLIENT_SECRET', default='')

ACCOUNT_ADAPTER = 'massageProject.accounts.adapters.ClosedSignupAccountAdapter'
SOCIALACCOUNT_ADAPTER = 'massageProject.accounts.adapters.GoogleSocialAccountAdapter'
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*']
ACCOUNT_EMAIL_VERIFICATION = 'none'
# Every new Google user must pass through the complete-profile form (phone is required).
SOCIALACCOUNT_AUTO_SIGNUP = False
SOCIALACCOUNT_FORMS = {'signup': 'massageProject.accounts.forms.SocialCompleteProfileForm'}
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': GOOGLE_OAUTH_CLIENT_ID,
            'secret': GOOGLE_OAUTH_CLIENT_SECRET,
        },
        'SCOPE': ['profile', 'email'],
    },
}
```

Note: `ACCOUNT_ADAPTER`/`SOCIALACCOUNT_ADAPTER` point at classes created in this task's Step 3 stub (fully implemented in Task 2) so `manage.py check` passes.

- [ ] **Step 3: Create adapter stubs so settings import cleanly**

Create `massageProject/accounts/adapters.py`:

```python
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class ClosedSignupAccountAdapter(DefaultAccountAdapter):
    pass


class GoogleSocialAccountAdapter(DefaultSocialAccountAdapter):
    pass
```

(Behavior is added test-first in Task 2.)

- [ ] **Step 4: Include allauth urls**

In `massageProject/accounts/urls.py`, add `include` to the imports and append the allauth include as the LAST entry of `urlpatterns` (order matters: the existing `path('login/', ...)` must shadow allauth's `account_login` page at the same route):

```python
from django.urls import include, path, reverse_lazy
```

```python
    path('reset/done/', PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html'
    ), name='password_reset_complete'),

    # allauth is appended last so the custom login/logout routes above win.
    # Provides google_login, google_callback, socialaccount_signup, etc.
    path('', include('allauth.urls')),
]
```

- [ ] **Step 5: Run system checks and migrate**

```bash
python manage.py check
python manage.py migrate
```

Expected: `System check identified no issues`, then migrations applied for `account` and `socialaccount` apps.

- [ ] **Step 6: Write the failing smoke tests**

Create `massageProject/accounts/tests_google_oauth.py`:

```python
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialLogin

User = get_user_model()

TEST_PROVIDERS = {
    'google': {
        'APP': {'client_id': 'test-client-id', 'secret': 'test-secret'},
        'SCOPE': ['profile', 'email'],
    },
}


def make_sociallogin(email, first_name='Иван', last_name='Петров', uid='google-uid-1'):
    """Build the SocialLogin object the Google adapter would produce after
    a successful OAuth callback, without talking to Google."""
    user = User(email=email, first_name=first_name, last_name=last_name)
    account = SocialAccount(provider='google', uid=uid, extra_data={'email': email})
    sociallogin = SocialLogin(user=user, account=account)
    sociallogin.email_addresses = [
        EmailAddress(email=email, verified=True, primary=True),
    ]
    return sociallogin


class GoogleCallbackTestMixin:
    """Drives a real /accounts/google/login/ -> callback round-trip with the
    Google token exchange mocked out."""

    def run_google_callback(self, sociallogin, next_url=''):
        data = {'next': next_url} if next_url else {}
        start = self.client.post(reverse('google_login'), data)
        self.assertEqual(start.status_code, 302)
        state = parse_qs(urlparse(start['Location']).query)['state'][0]
        with patch(
            'allauth.socialaccount.providers.google.views.GoogleOAuth2Adapter.complete_login',
            return_value=sociallogin,
        ), patch(
            'allauth.socialaccount.providers.oauth2.client.OAuth2Client.get_access_token',
            return_value={'access_token': 'dummy-token'},
        ):
            return self.client.get(
                reverse('google_callback'), {'code': 'dummy-code', 'state': state}
            )


@override_settings(SOCIALACCOUNT_PROVIDERS=TEST_PROVIDERS)
class GoogleWiringTests(TestCase):
    def test_google_login_redirects_to_google(self):
        response = self.client.post(reverse('google_login'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            response['Location'].startswith('https://accounts.google.com/o/oauth2/'),
            response['Location'],
        )

    def test_existing_login_route_still_serves_custom_view(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/auth_entry.html')
```

- [ ] **Step 7: Run the tests**

```bash
python manage.py test massageProject.accounts.tests_google_oauth -v 2
```

Expected: both tests PASS (the wiring from Steps 1–5 is already in place; if `google_login` reverses to nothing or redirects elsewhere, fix the wiring before moving on). Then run the full accounts suite to prove nothing regressed:

```bash
python manage.py test massageProject.accounts
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add requirements.txt massageProject/settings.py massageProject/accounts/urls.py massageProject/accounts/adapters.py massageProject/accounts/tests_google_oauth.py
git commit -m "feat: wire django-allauth with the Google provider"
```

---

### Task 2: Adapters — close local allauth signup, auto-link Google logins by email

**Files:**
- Modify: `massageProject/accounts/adapters.py`
- Test: `massageProject/accounts/tests_google_oauth.py`

**Interfaces:**
- Consumes: `TEST_PROVIDERS`, `make_sociallogin`, `GoogleCallbackTestMixin` from Task 1's test file; `User.objects.create_user(email, phone_number, password)` from `AppUserManager`.
- Produces: `ClosedSignupAccountAdapter.is_open_for_signup() -> False`; `GoogleSocialAccountAdapter.pre_social_login(request, sociallogin)` which connects the sociallogin to an existing `CustomUser` matched by verified email. Later tasks rely on: an unknown Google email reaching the `socialaccount_signup` view.

- [ ] **Step 1: Write the failing tests**

Append to `massageProject/accounts/tests_google_oauth.py`:

```python
@override_settings(SOCIALACCOUNT_PROVIDERS=TEST_PROVIDERS)
class AdapterTests(GoogleCallbackTestMixin, TestCase):
    def test_local_allauth_signup_is_closed(self):
        response = self.client.get(reverse('account_signup'))
        self.assertTemplateUsed(response, 'account/signup_closed.html')

    def test_google_login_with_known_email_links_and_logs_in(self):
        user = User.objects.create_user(
            email='known@example.com', phone_number='0899123456', password='Str0ng-pass1',
        )
        response = self.run_google_callback(make_sociallogin('known@example.com'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)
        self.assertTrue(
            SocialAccount.objects.filter(user=user, provider='google').exists()
        )

    def test_returning_google_user_logs_straight_in(self):
        user = User.objects.create_user(
            email='returning@example.com', phone_number='0899123457', password='Str0ng-pass1',
        )
        SocialAccount.objects.create(user=user, provider='google', uid='google-uid-1')
        response = self.run_google_callback(make_sociallogin('returning@example.com'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

    def test_unknown_email_is_sent_to_complete_profile(self):
        response = self.run_google_callback(make_sociallogin('newcomer@gmail.com'))
        self.assertRedirects(
            response, reverse('socialaccount_signup'), fetch_redirect_response=False
        )
        self.assertEqual(User.objects.count(), 0)
```

- [ ] **Step 2: Run tests to verify the interesting ones fail**

```bash
python manage.py test massageProject.accounts.tests_google_oauth.AdapterTests -v 2
```

Expected: `test_local_allauth_signup_is_closed` FAILS (allauth's open signup page is used instead of `signup_closed.html`); `test_google_login_with_known_email_links_and_logs_in` FAILS (without auto-link, the flow bounces to the signup form instead of logging in — the session has no `_auth_user_id`). The other two may already pass.

- [ ] **Step 3: Implement the adapters**

Replace the whole body of `massageProject/accounts/adapters.py`:

```python
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model


class ClosedSignupAccountAdapter(DefaultAccountAdapter):
    """Local (email/password) allauth signup stays closed -- registration
    happens through the booking auth modal, which enforces OTP verification
    and the phone-number requirement."""

    def is_open_for_signup(self, request):
        return False


class GoogleSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Auto-link a first-time Google login to an existing account with the
    same email. Existing users have no allauth EmailAddress records, so the
    built-in SOCIALACCOUNT_EMAIL_AUTHENTICATION matching would never find
    them; we match on CustomUser.email directly. Only provider-verified
    emails are trusted (Google always verifies)."""

    def pre_social_login(self, request, sociallogin):
        if sociallogin.is_existing:
            return
        verified_emails = [
            address.email.lower()
            for address in sociallogin.email_addresses
            if address.verified
        ]
        if not verified_emails:
            return
        User = get_user_model()
        user = User.objects.filter(email__iexact=verified_emails[0]).first()
        if user is not None:
            sociallogin.connect(request, user)
```

- [ ] **Step 4: Run the tests**

```bash
python manage.py test massageProject.accounts.tests_google_oauth -v 2
```

Expected: all Task 1 + Task 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add massageProject/accounts/adapters.py massageProject/accounts/tests_google_oauth.py
git commit -m "feat: close local allauth signup and auto-link Google logins by email"
```

---

### Task 3: `SocialCompleteProfileForm`

**Files:**
- Modify: `massageProject/accounts/forms.py`
- Test: `massageProject/accounts/tests_google_oauth.py`

**Interfaces:**
- Consumes: `make_sociallogin` from Task 1; `PhoneClaimFormMixin.error_messages['already_registered']` (reused message, not the mixin itself — it targets `ModelForm.instance`, which allauth's signup form doesn't have); phone validators from `CustomUser._meta.get_field('phone_number').validators`; `User.objects.normalize_phone_number`.
- Produces: `SocialCompleteProfileForm(data=..., sociallogin=...)` with fields `email` (disabled), `first_name`, `last_name`, `phone_number`, `date_of_birth`; `save(request) -> CustomUser`. Registered in settings since Task 1 via `SOCIALACCOUNT_FORMS['signup']`. Task 4's template renders exactly these five bound fields.

- [ ] **Step 1: Write the failing tests**

Append to `massageProject/accounts/tests_google_oauth.py`:

```python
from massageProject.accounts.forms import SocialCompleteProfileForm


@override_settings(SOCIALACCOUNT_PROVIDERS=TEST_PROVIDERS)
class SocialCompleteProfileFormTests(TestCase):
    def form(self, data=None, email='newcomer@gmail.com'):
        return SocialCompleteProfileForm(data=data, sociallogin=make_sociallogin(email))

    def test_names_are_prefilled_from_google(self):
        form = self.form()
        self.assertEqual(form.initial.get('first_name'), 'Иван')
        self.assertEqual(form.initial.get('last_name'), 'Петров')

    def test_phone_is_required(self):
        form = self.form(data={
            'email': 'newcomer@gmail.com', 'first_name': 'Иван',
            'last_name': 'Петров', 'phone_number': '',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('phone_number', form.errors)

    def test_invalid_phone_format_is_rejected(self):
        form = self.form(data={
            'email': 'newcomer@gmail.com', 'first_name': 'Иван',
            'last_name': 'Петров', 'phone_number': '123456',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('phone_number', form.errors)

    def test_phone_is_normalized(self):
        form = self.form(data={
            'email': 'newcomer@gmail.com', 'first_name': 'Иван',
            'last_name': 'Петров', 'phone_number': '+359899123456',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['phone_number'], '0899123456')

    def test_date_of_birth_is_optional(self):
        form = self.form(data={
            'email': 'newcomer@gmail.com', 'first_name': 'Иван',
            'last_name': 'Петров', 'phone_number': '0899123456',
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_phone_of_registered_user_is_rejected(self):
        User.objects.create_user(
            email='taken@example.com', phone_number='0899123456', password='Str0ng-pass1',
        )
        form = self.form(data={
            'email': 'newcomer@gmail.com', 'first_name': 'Иван',
            'last_name': 'Петров', 'phone_number': '0899123456',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('phone_number', form.errors)

    def test_phone_of_passwordless_user_is_claimable(self):
        staff_created = User.objects.create_user(
            email='placeholder@example.com', phone_number='0899123456', password=None,
        )
        form = self.form(data={
            'email': 'newcomer@gmail.com', 'first_name': 'Иван',
            'last_name': 'Петров', 'phone_number': '0899123456',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form._claimed_user, staff_created)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python manage.py test massageProject.accounts.tests_google_oauth.SocialCompleteProfileFormTests -v 2
```

Expected: FAIL at import time — `ImportError: cannot import name 'SocialCompleteProfileForm'`.

- [ ] **Step 3: Implement the form**

In `massageProject/accounts/forms.py`, add to the imports at the top:

```python
from allauth.socialaccount.forms import SignupForm as SocialSignupFormBase
```

Then append the form class at the end of the file:

```python
class SocialCompleteProfileForm(SocialSignupFormBase):
    """Complete-profile step shown to first-time Google users: Google supplies
    a verified email and names, but reservations need a phone number."""

    first_name = forms.CharField(label=_('Име'), max_length=50)
    last_name = forms.CharField(label=_('Фамилия'), max_length=50)
    phone_number = forms.CharField(
        label=_('Телефон'),
        max_length=15,
        validators=get_user_model()._meta.get_field('phone_number').validators,
        widget=forms.TextInput(attrs={'placeholder': '0899999999'}),
    )
    date_of_birth = forms.DateField(
        label=_('Дата на раждане (незадължително)'),
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._claimed_user = None
        # The email comes verified from Google and must not be edited.
        if 'email' in self.fields:
            self.fields['email'].disabled = True
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'auth-modal-input')

    def clean_phone_number(self):
        phone_number = self.cleaned_data['phone_number']
        User = get_user_model()
        normalized = User.objects.normalize_phone_number(phone_number)
        try:
            existing_user = User.objects.get(phone_number__iexact=normalized)
        except User.DoesNotExist:
            pass
        else:
            if existing_user.has_usable_password():
                raise ValidationError(
                    PhoneClaimFormMixin.error_messages['already_registered']
                )
            self._claimed_user = existing_user
        return normalized

    def save(self, request):
        if self._claimed_user is not None:
            # A passwordless (staff-created) record owns this phone number:
            # claim it instead of creating a duplicate. The verified Google
            # email wins, mirroring BookingRegistrationForm.save().
            user = self._claimed_user
            user.first_name = self.cleaned_data['first_name']
            user.last_name = self.cleaned_data['last_name']
            user.phone_number = self.cleaned_data['phone_number']
            if self.cleaned_data.get('date_of_birth'):
                user.date_of_birth = self.cleaned_data['date_of_birth']
            user.email = self.sociallogin.user.email or user.email
            user.is_active = True
            user.save()
            self.sociallogin.connect(request, user)
            return user

        # Set the extra fields on the pending user BEFORE the allauth adapter
        # saves it, so the row never exists without a phone number. The
        # adapter copies first/last name and email from cleaned_data itself.
        self.sociallogin.user.phone_number = self.cleaned_data['phone_number']
        self.sociallogin.user.date_of_birth = self.cleaned_data.get('date_of_birth')
        return super().save(request)
```

(`forms`, `get_user_model`, `ValidationError`, `_`, and `PhoneClaimFormMixin` are already imported/defined in this file.)

- [ ] **Step 4: Run the tests**

```bash
python manage.py test massageProject.accounts.tests_google_oauth -v 2
```

Expected: all PASS. If `test_names_are_prefilled_from_google` fails because `form.initial` lacks names, check `DefaultSocialAccountAdapter.get_signup_form_initial_data` in the installed allauth version and prefill explicitly in `__init__` instead:

```python
        user = self.sociallogin.user
        self.initial.setdefault('first_name', user.first_name)
        self.initial.setdefault('last_name', user.last_name)
```

- [ ] **Step 5: Commit**

```bash
git add massageProject/accounts/forms.py massageProject/accounts/tests_google_oauth.py
git commit -m "feat: add the Google complete-profile signup form"
```

---

### Task 4: Complete-profile page template + end-to-end signup flow

**Files:**
- Create: `templates/socialaccount/signup.html`
- Modify: `staticfiles/css/components/auth-modal.css`
- Test: `massageProject/accounts/tests_google_oauth.py`

**Interfaces:**
- Consumes: `run_google_callback` / `make_sociallogin` from Task 1; the five form fields from Task 3; existing CSS classes `auth-modal`, `auth-modal-title`, `auth-modal-subtitle`, `auth-modal-field`, `auth-modal-label`, `auth-modal-input`, `auth-modal-error`, `btn btn-primary auth-modal-submit`.
- Produces: `.auth-page` CSS wrapper class (reused by Task 6's templates); the rendered page at url name `socialaccount_signup`.

- [ ] **Step 1: Write the failing flow tests**

Append to `massageProject/accounts/tests_google_oauth.py`:

```python
@override_settings(SOCIALACCOUNT_PROVIDERS=TEST_PROVIDERS)
class CompleteProfileFlowTests(GoogleCallbackTestMixin, TestCase):
    def start_signup(self, email='newcomer@gmail.com', next_url=''):
        response = self.run_google_callback(make_sociallogin(email), next_url=next_url)
        self.assertRedirects(
            response, reverse('socialaccount_signup'), fetch_redirect_response=False
        )

    def test_complete_profile_page_renders_prefilled(self):
        self.start_signup()
        response = self.client.get(reverse('socialaccount_signup'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'socialaccount/signup.html')
        self.assertContains(response, 'Иван')
        self.assertContains(response, 'newcomer@gmail.com')

    def test_submitting_profile_creates_user_and_logs_in(self):
        self.start_signup()
        response = self.client.post(reverse('socialaccount_signup'), {
            'email': 'newcomer@gmail.com',
            'first_name': 'Иван',
            'last_name': 'Петров',
            'phone_number': '0899111222',
            'date_of_birth': '',
        })
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email='newcomer@gmail.com')
        self.assertEqual(user.phone_number, '0899111222')
        self.assertEqual(user.first_name, 'Иван')
        self.assertFalse(user.has_usable_password())
        self.assertTrue(user.is_active)
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)
        self.assertTrue(
            SocialAccount.objects.filter(user=user, provider='google').exists()
        )

    def test_next_is_honored_after_signup(self):
        next_url = reverse('reservation_page')
        self.start_signup(next_url=next_url)
        response = self.client.post(reverse('socialaccount_signup'), {
            'email': 'newcomer@gmail.com',
            'first_name': 'Иван',
            'last_name': 'Петров',
            'phone_number': '0899111222',
            'date_of_birth': '',
        })
        self.assertRedirects(response, next_url, fetch_redirect_response=False)

    def test_invalid_phone_re_renders_with_error(self):
        self.start_signup()
        response = self.client.post(reverse('socialaccount_signup'), {
            'email': 'newcomer@gmail.com',
            'first_name': 'Иван',
            'last_name': 'Петров',
            'phone_number': 'not-a-phone',
            'date_of_birth': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 0)
        self.assertContains(response, 'auth-modal-error')

    def test_claiming_staff_created_user_updates_instead_of_duplicating(self):
        staff_created = User.objects.create_user(
            email='placeholder@example.com', phone_number='0899111222', password=None,
        )
        self.start_signup()
        self.client.post(reverse('socialaccount_signup'), {
            'email': 'newcomer@gmail.com',
            'first_name': 'Иван',
            'last_name': 'Петров',
            'phone_number': '0899111222',
            'date_of_birth': '',
        })
        self.assertEqual(User.objects.count(), 1)
        staff_created.refresh_from_db()
        self.assertEqual(staff_created.email, 'newcomer@gmail.com')
        self.assertEqual(int(self.client.session['_auth_user_id']), staff_created.pk)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python manage.py test massageProject.accounts.tests_google_oauth.CompleteProfileFlowTests -v 2
```

Expected: `test_complete_profile_page_renders_prefilled` FAILS on `assertTemplateUsed` (allauth's bundled template renders instead of ours) or on the `auth-modal-error`/content assertions. The POST tests may pass already (allauth's default template posts the same fields) — the template assertions are the gate.

- [ ] **Step 3: Create the template**

Create `templates/socialaccount/signup.html`:

```html
{% extends 'base.html' %}
{% load i18n %}
{% block content %}
<div class="auth-page">
  <div class="auth-modal">
    <h2 class="auth-modal-title">{% trans "Завършете профила си" %}</h2>
    <p class="auth-modal-subtitle">{% trans "Влязохте с Google. Трябва ни само телефонен номер за връзка при резервации." %}</p>
    <form method="post" action="{% url 'socialaccount_signup' %}">
      {% csrf_token %}
      {% for error in form.non_field_errors %}
        <p class="auth-modal-error">{{ error }}</p>
      {% endfor %}
      <div class="auth-modal-field">
        <label class="auth-modal-label" for="{{ form.email.id_for_label }}">{% trans "Имейл" %}</label>
        {{ form.email }}
      </div>
      <div class="auth-modal-field">
        <label class="auth-modal-label" for="{{ form.first_name.id_for_label }}">{{ form.first_name.label }}</label>
        {{ form.first_name }}
        {% for error in form.first_name.errors %}<p class="auth-modal-error">{{ error }}</p>{% endfor %}
      </div>
      <div class="auth-modal-field">
        <label class="auth-modal-label" for="{{ form.last_name.id_for_label }}">{{ form.last_name.label }}</label>
        {{ form.last_name }}
        {% for error in form.last_name.errors %}<p class="auth-modal-error">{{ error }}</p>{% endfor %}
      </div>
      <div class="auth-modal-field">
        <label class="auth-modal-label" for="{{ form.phone_number.id_for_label }}">{{ form.phone_number.label }}</label>
        {{ form.phone_number }}
        {% for error in form.phone_number.errors %}<p class="auth-modal-error">{{ error }}</p>{% endfor %}
      </div>
      <div class="auth-modal-field">
        <label class="auth-modal-label" for="{{ form.date_of_birth.id_for_label }}">{{ form.date_of_birth.label }}</label>
        {{ form.date_of_birth }}
        {% for error in form.date_of_birth.errors %}<p class="auth-modal-error">{{ error }}</p>{% endfor %}
      </div>
      {{ redirect_field }}
      <button type="submit" class="btn btn-primary auth-modal-submit">{% trans "Продължи" %}</button>
    </form>
  </div>
</div>
{% endblock %}
```

Note: `{{ redirect_field }}` is provided by allauth's signup view context (a hidden `next` input); if the installed allauth version doesn't provide it, replace that line with nothing — the `next` url also survives via the stashed sociallogin state, which `test_next_is_honored_after_signup` verifies.

- [ ] **Step 4: Add the standalone-page CSS**

Append to `staticfiles/css/components/auth-modal.css`:

```css
/* Standalone auth pages (Google complete-profile, OAuth errors) reuse the
   modal card outside of an overlay. */
.auth-page {
    display: flex;
    justify-content: center;
    padding: 4rem 1rem;
}

.auth-page .auth-modal {
    box-shadow: 0 8px 30px rgba(74, 55, 40, 0.12);
}
```

- [ ] **Step 5: Run the tests**

```bash
python manage.py test massageProject.accounts.tests_google_oauth -v 2
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add templates/socialaccount/signup.html staticfiles/css/components/auth-modal.css massageProject/accounts/tests_google_oauth.py
git commit -m "feat: add the Google complete-profile page"
```

---

### Task 5: "Continue with Google" button on the modal email step

**Files:**
- Modify: `templates/partials/auth_modal.html`
- Modify: `staticfiles/css/components/auth-modal.css`
- Test: `massageProject/accounts/tests_google_oauth.py`

**Interfaces:**
- Consumes: url name `google_login` (Task 1); modal JS `state.next` and the `open()` function in `auth_modal.html`.
- Produces: hidden input `#auth-google-next` inside a POST form on the email step; JS keeps it in sync with `state.next`.

- [ ] **Step 1: Write the failing test**

Append to `massageProject/accounts/tests_google_oauth.py`:

```python
@override_settings(SOCIALACCOUNT_PROVIDERS=TEST_PROVIDERS)
class AuthModalGoogleButtonTests(TestCase):
    def test_modal_email_step_contains_google_form(self):
        response = self.client.get(reverse('login'))
        self.assertContains(response, 'id="auth-google-next"')
        self.assertContains(response, reverse('google_login'))
        self.assertContains(response, 'auth-modal-google-btn')
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python manage.py test massageProject.accounts.tests_google_oauth.AuthModalGoogleButtonTests -v 2
```

Expected: FAIL — `auth-google-next` not found in the response.

- [ ] **Step 3: Add the button to the email step**

In `templates/partials/auth_modal.html`, inside `<div class="auth-modal-step" data-step="email">`, directly after the `<button ... id="auth-email-continue">…</button>` line, add:

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

- [ ] **Step 4: Propagate `state.next` into the Google form**

In the same file's `<script>` block, inside the `open(opts)` function, directly after `state.next = opts.next || '';`, add:

```javascript
        var googleNext = document.getElementById('auth-google-next');
        if (googleNext) googleNext.value = state.next;
```

- [ ] **Step 5: Add the button and divider CSS**

Append to `staticfiles/css/components/auth-modal.css`:

```css
.auth-modal-divider {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin: 1.25rem 0;
    color: var(--text-muted);
    font-size: 0.8rem;
}

.auth-modal-divider::before,
.auth-modal-divider::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--hp-border);
}

.auth-modal-google-btn {
    display: flex;
    width: 100%;
    align-items: center;
    justify-content: center;
    gap: 0.6rem;
    padding: 0.75rem 1rem;
    border: 1.5px solid var(--hp-border);
    border-radius: 8px;
    background: #fff;
    font-size: 0.95rem;
    cursor: pointer;
}

.auth-modal-google-btn:hover {
    background: #f7f5f2;
}
```

- [ ] **Step 6: Run the tests**

```bash
python manage.py test massageProject.accounts.tests_google_oauth -v 2
python manage.py test massageProject.accounts
```

Expected: all PASS (including the pre-existing modal e2e tests — the new markup must not break them).

- [ ] **Step 7: Visual check**

```bash
python manage.py runserver
```

Open `http://localhost:8000/bg/accounts/login/` — the modal must show the email input, then an "или" divider, then a white Google button with the colored G logo. (Clicking it without real credentials will bounce at Google — that's expected until Task 7's console setup.)

- [ ] **Step 8: Commit**

```bash
git add templates/partials/auth_modal.html staticfiles/css/components/auth-modal.css massageProject/accounts/tests_google_oauth.py
git commit -m "feat: add the Continue with Google button to the auth modal"
```

---

### Task 6: Branded error/cancel/inactive pages

**Files:**
- Create: `templates/socialaccount/authentication_error.html`
- Create: `templates/socialaccount/login_cancelled.html`
- Create: `templates/account/inactive.html`
- Test: `massageProject/accounts/tests_google_oauth.py`

**Interfaces:**
- Consumes: `.auth-page` CSS (Task 4); `run_google_callback` (Task 1); url name `index` (home page, from `main_app.urls`).
- Produces: nothing consumed later — these are terminal pages.

- [ ] **Step 1: Write the failing tests**

Append to `massageProject/accounts/tests_google_oauth.py`:

```python
@override_settings(SOCIALACCOUNT_PROVIDERS=TEST_PROVIDERS)
class BrandedAllauthPagesTests(GoogleCallbackTestMixin, TestCase):
    def test_authentication_error_page_is_branded(self):
        # Hitting the callback with no state/code triggers the error page.
        response = self.client.get(reverse('google_callback'))
        self.assertTemplateUsed(response, 'socialaccount/authentication_error.html')
        self.assertContains(
            response, 'auth-page', status_code=response.status_code
        )

    def test_login_cancelled_page_is_branded(self):
        response = self.client.get(reverse('socialaccount_login_cancelled'))
        self.assertTemplateUsed(response, 'socialaccount/login_cancelled.html')
        self.assertContains(response, 'auth-page')

    def test_inactive_user_lands_on_branded_inactive_page(self):
        User.objects.create_user(
            email='inactive@example.com', phone_number='0899123458',
            password='Str0ng-pass1', is_active=False,
        )
        response = self.run_google_callback(make_sociallogin('inactive@example.com'))
        self.assertRedirects(
            response, reverse('account_inactive'), fetch_redirect_response=False
        )
        page = self.client.get(reverse('account_inactive'))
        self.assertTemplateUsed(page, 'account/inactive.html')
        self.assertContains(page, 'auth-page')
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python manage.py test massageProject.accounts.tests_google_oauth.BrandedAllauthPagesTests -v 2
```

Expected: FAIL — allauth's bundled templates render without the `auth-page` class. (If `test_authentication_error_page_is_branded` fails because the callback redirects instead of rendering, adjust the assertion to follow the redirect: allauth versions differ on whether errors render in place or redirect; the template-used assertion on the final response is the contract.)

- [ ] **Step 3: Create the three templates**

Create `templates/socialaccount/authentication_error.html`:

```html
{% extends 'base.html' %}
{% load i18n %}
{% block content %}
<div class="auth-page">
  <div class="auth-modal">
    <h2 class="auth-modal-title">{% trans "Възникна проблем при входа с Google." %}</h2>
    <p class="auth-modal-subtitle">{% trans "Опитайте отново или влезте с имейл и код." %}</p>
    <a class="btn btn-primary auth-modal-submit" href="{% url 'login' %}">{% trans "Опитайте отново" %}</a>
    <p class="auth-modal-footnote"><a href="{% url 'index' %}">{% trans "Към началната страница" %}</a></p>
  </div>
</div>
{% endblock %}
```

Create `templates/socialaccount/login_cancelled.html`:

```html
{% extends 'base.html' %}
{% load i18n %}
{% block content %}
<div class="auth-page">
  <div class="auth-modal">
    <h2 class="auth-modal-title">{% trans "Входът с Google беше отменен." %}</h2>
    <p class="auth-modal-subtitle">{% trans "Опитайте отново или влезте с имейл и код." %}</p>
    <a class="btn btn-primary auth-modal-submit" href="{% url 'login' %}">{% trans "Опитайте отново" %}</a>
    <p class="auth-modal-footnote"><a href="{% url 'index' %}">{% trans "Към началната страница" %}</a></p>
  </div>
</div>
{% endblock %}
```

Create `templates/account/inactive.html`:

```html
{% extends 'base.html' %}
{% load i18n %}
{% block content %}
<div class="auth-page">
  <div class="auth-modal">
    <h2 class="auth-modal-title">{% trans "Този профил е деактивиран." %}</h2>
    <p class="auth-modal-subtitle">{% trans "Моля, потвърдете имейла си, преди да влезете. Проверете пощата си за линк за потвърждение, или поискайте нов по-долу." %}</p>
    <p class="auth-modal-footnote"><a href="{% url 'index' %}">{% trans "Към началната страница" %}</a></p>
  </div>
</div>
{% endblock %}
```

(The subtitle string in `inactive.html` deliberately reuses the existing `CustomAuthenticationForm.error_messages['inactive']` wording so no new translation is needed for it. The home page url name `index` is confirmed in `massageProject/main_app/urls.py:8`.)

- [ ] **Step 4: Run the tests**

```bash
python manage.py test massageProject.accounts.tests_google_oauth -v 2
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add templates/socialaccount/ templates/account/ massageProject/accounts/tests_google_oauth.py
git commit -m "feat: brand the allauth error, cancelled, and inactive pages"
```

---

### Task 7: Translations and setup documentation

**Files:**
- Modify: `locale/bg/LC_MESSAGES/django.po`, `locale/en/LC_MESSAGES/django.po`
- Modify: `README.md`

**Interfaces:**
- Consumes: every `{% trans %}` / `_()` string introduced in Tasks 3–6.
- Produces: compiled `.mo` files; README setup section.

- [ ] **Step 1: Extract messages**

```bash
source venv/bin/activate
python manage.py makemessages -l bg -l en
```

- [ ] **Step 2: Translate the new msgids**

New msgids and their **English** translations for `locale/en/LC_MESSAGES/django.po` (for `locale/bg/LC_MESSAGES/django.po`, follow the existing convention in that file — msgids are already Bulgarian, so match how other entries handle bg msgstr; also clear any `#, fuzzy` flags makemessages adds to these entries in BOTH files):

| msgid (bg) | msgstr (en) |
|---|---|
| `или` | `or` |
| `Продължи с Google` | `Continue with Google` |
| `Завършете профила си` | `Complete your profile` |
| `Влязохте с Google. Трябва ни само телефонен номер за връзка при резервации.` | `You signed in with Google. We just need a phone number to contact you about your reservations.` |
| `Възникна проблем при входа с Google.` | `Something went wrong while signing in with Google.` |
| `Опитайте отново или влезте с имейл и код.` | `Try again or sign in with your email and a code.` |
| `Опитайте отново` | `Try again` |
| `Входът с Google беше отменен.` | `Google sign-in was cancelled.` |
| `Този профил е деактивиран.` | `This account is inactive.` |
| `Към началната страница` | `Back to the home page` |

(`Име`, `Фамилия`, `Телефон`, `Имейл`, `Продължи`, `Дата на раждане (незадължително)`, and the already-registered phone message are pre-existing msgids — verify they are already translated, don't duplicate them.)

- [ ] **Step 3: Compile and verify**

```bash
python manage.py compilemessages
python manage.py test massageProject.accounts
```

Expected: compile succeeds; full accounts suite passes.

- [ ] **Step 4: Check the English rendering**

```bash
python manage.py runserver
```

Open `http://localhost:8000/en/accounts/login/` — the modal shows "Continue with Google" and "or" in English.

- [ ] **Step 5: Document the Google Cloud Console setup in README.md**

Append this section to `README.md`:

```markdown
## Google OAuth setup ("Continue with Google")

1. In [Google Cloud Console](https://console.cloud.google.com/) create (or pick) a project, then
   **APIs & Services → Credentials → Create Credentials → OAuth client ID** (type: *Web application*).
   Configure the OAuth consent screen first if prompted (External, app name, support email).
2. Add **Authorized redirect URIs** for every language prefix and host:
   - `http://localhost:8000/bg/accounts/google/login/callback/`
   - `http://localhost:8000/en/accounts/google/login/callback/`
   - the same two paths on the production domain, over `https`.
3. Put the credentials in `.env`:

   ```
   GOOGLE_OAUTH_CLIENT_ID=<client id>.apps.googleusercontent.com
   GOOGLE_OAUTH_CLIENT_SECRET=<client secret>
   ```

4. Restart the server. The button lives on the login/register modal.
```

- [ ] **Step 6: Manual end-to-end verification (requires real credentials in `.env`)**

With real credentials configured:
1. Open the site logged out, click "Book Now" → modal → "Продължи с Google" → pick a Google account **not** registered on the site → land on the complete-profile page with names prefilled → submit a valid phone → end up logged in, back on the reservation page.
2. Log out, repeat with the same Google account → logged straight in (no profile step).
3. Repeat with a Google account whose email matches an existing site user → logged straight in, and the admin shows a Social Account linked to that user.

If credentials aren't available yet, note it and rely on the automated suite.

- [ ] **Step 7: Commit**

```bash
git add locale/ README.md
git commit -m "i18n: translate the Google OAuth strings; docs: Google OAuth setup"
```

---

## Self-Review Notes

- **Spec coverage:** button on the modal (Task 5); allauth wiring (Task 1); complete-profile with required phone, prefills, optional DOB, no password (Tasks 3–4); auto-link by email (Task 2); env credentials + console instructions (Tasks 1, 7); i18n per CLAUDE.md (Task 7).
- **Known version-sensitivity:** the mocked-callback test harness (`run_google_callback`) patches `GoogleOAuth2Adapter.complete_login` and `OAuth2Client.get_access_token` — stable across recent allauth versions, but if a signature changed in the installed version, fix the patch targets rather than weakening assertions. Same for `form.initial` name prefill (fallback given in Task 3 Step 4) and `{{ redirect_field }}` (fallback given in Task 4 Step 3).
- **Deliberately out of scope (per user decisions):** button on the choice step or `auth_entry.html` no-JS page; making phone optional; account-connections management UI; storing OAuth tokens.

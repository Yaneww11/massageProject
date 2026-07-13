# Email-First Login/Signup Modal for Booking — Design

## 1. Problem & Goal

Today, an anonymous visitor who clicks any "Book Now" link (or the header "Login" link) is redirected to a full-page `/accounts/login/`, which itself links to a full-page `/accounts/register/`. Registration requires clicking a link emailed to the user before the account becomes usable.

Goal: replace that entire flow with a single modal, opened in-place (no page reload) from any "Book Now" link or the header "Login" link, that:

1. Asks only for an email address first.
2. If an account exists with that email, lets the user choose password login or a one-time emailed code.
3. If no account exists, emails a one-time code immediately and, once confirmed, shows a short registration form (first name, last name, phone number, password; date of birth optional).
4. Defends the code-sending and registration endpoints against bots/spam (rate limiting, honeypot, Cloudflare Turnstile).
5. On success, sends the user to whatever booking URL they originally clicked (preserving e.g. a specific massage's booking page).

## 2. Scope

**In scope:**
- New email-first modal (email → branch → code-or-password → registration → success).
- New backend endpoints backing each modal step.
- Rate limiting (django-ratelimit) and bot defense (honeypot + Cloudflare Turnstile) on the sensitive endpoints.
- Removal of the old full-page login/register flow and the old link-click email verification flow, since the modal fully replaces both.
- `date_of_birth` field added to `CustomUser` (optional).
- Translation updates (bg/en) for all new user-facing strings.

**Explicitly out of scope (separate follow-up plan):**
- "Continue with Google" — not rendered at all in this plan. Will be added later via `django-allauth` in its own plan, since it has independent infrastructure (OAuth credentials, callback URL) and shouldn't block this one.

**Untouched by this plan:**
- `BrandedPasswordResetView` and its templates — forgot-password remains its own full-page flow, linked from the modal's password step.
- `ReservationPage` / `MessageReservation` — booking still requires an authenticated user; no anonymous booking, no schema change to reservations. Anonymous users never see the booking wizard; the modal intercepts the click before navigation.
- Legacy accounts with `is_active=False` from the old flow — left as-is. They still get blocked with the existing "please verify your email" message on login (password or code). No reactivation path is built here.

## 3. Data model changes

### 3.1 `accounts.CustomUser`
Add:
```python
date_of_birth = models.DateField(null=True, blank=True)
```
One migration. No validation beyond Django's default DateField parsing — no minimum-age rule was requested.

### 3.2 New model: `accounts.EmailOTP`
```python
class EmailOTP(models.Model):
    PURPOSE_SIGNUP = 'signup'
    PURPOSE_LOGIN = 'login'
    PURPOSE_CHOICES = [(PURPOSE_SIGNUP, 'Signup'), (PURPOSE_LOGIN, 'Login')]

    email = models.EmailField(db_index=True)
    code_hash = models.CharField(max_length=128)
    purpose = models.CharField(max_length=10, choices=PURPOSE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)
```
- Code is a 6-digit numeric string, stored only as a hash (e.g. Django's `make_password`/`check_password`), never plaintext, so a DB read can't leak usable codes.
- `expires_at` = created_at + 10 minutes.
- `attempts` capped at 5; once exceeded, the row is treated as dead and the user must request a new code (via `send-code` again, which is itself rate-limited).
- A row is "live" if `consumed_at is None`, `attempts < 5`, and `expires_at > now`.
- No cleanup/cron job in this plan — dead rows are simply filtered out of queries, not deleted.

## 4. Backend endpoints

All new views live in `accounts` app, under a new `accounts/urls.py` prefix (e.g. `/accounts/auth-modal/...`), JSON in/out, standard Django CSRF (the modal fetches the CSRF cookie/token like any other same-origin JS on the site).

| Endpoint | Input | Behavior |
|---|---|---|
| `POST check-email/` | `{email}` | Returns `{exists: bool}`. No rate limit needed beyond the general one on `send-code` since this alone can't send email or create accounts. |
| `POST send-code/` | `{email, turnstile_token}` | Verifies Turnstile token server-side against Cloudflare's siteverify API. Rate-limited per-IP and per-email (django-ratelimit). Creates an `EmailOTP` row (purpose inferred by whether `check-email` said the account exists) and emails the code via the existing `GmailBackend`. |
| `POST verify-code/` | `{email, code}` | Looks up the newest live `EmailOTP` for that email; increments `attempts` on mismatch. On match: marks `consumed_at`. If an existing user owns that email, logs them in via `VerificationAwareBackend` (same `is_active` gating as password login) and returns `{status: 'logged_in', redirect: <url>}`. If no user owns that email, sets `request.session['verified_signup_email'] = email` with a 15-minute expiry stamp and returns `{status: 'verified', next: 'register'}`. |
| `POST login-password/` | `{email, password}` | Wraps existing `CustomAuthenticationForm`/`authenticate()`. Rate-limited per-IP and per-email. |
| `POST register/` | `{first_name, last_name, phone_number, password, date_of_birth?, middle_name (honeypot), turnstile_token}` | Requires `request.session['verified_signup_email']` present and unexpired, else 403. Honeypot: if `middle_name` is non-empty, return a fake success without creating anything. Verifies Turnstile token. Reuses `CustomUserForm`'s field validation, including its existing `clean_phone_number` "claim a pre-existing passwordless record" logic. Creates the user with `email` from the session (not client input, to prevent registering an unverified address) and `is_active=True` immediately. Logs the user in and returns `{status: 'registered', redirect: <url>}`. Rate-limited per-IP. |

**Redirect target:** every success response carries the URL the user originally tried to reach — the frontend passes along whatever `?next=` the intercepted link pointed to (defaulting to `reservation_page` for the header "Login" link with no specific target), so clicking "Book Now" on a specific massage still lands the user on that massage's booking page afterward.

## 5. Removed

- `UserRegisterView`, `VerifyEmailView`, `ResendVerificationView`, `ResendVerificationForm`.
- Templates: `registration/verification_sent.html`, `registration/resend_verification.html`, `registration/login.html`, `registration/register.html` (superseded by the modal; if any of these templates are extended/included elsewhere they'll be checked during implementation before deletion).
- URL entries for `register/`, `login/` (full-page), `verification-sent/`, `verify/<uidb64>/<token>/`, `resend-verification/`.
- `EmailVerificationTokenGenerator` (`accounts/tokens.py`) and its usage — it is specific to link-based signup verification, distinct from the generator Django's built-in `PasswordResetView` uses internally for password reset, so removing it does not affect password reset.
- The dead `{% if not user.is_authenticated %}` / `.bn-unauth` branch in `templates/pages/reservation.html`, since anonymous users now never reach that template (the modal intercepts before navigation).

`LoginView`/`LogoutView`/`BrandedPasswordResetView` and their URLs stay — password reset remains a full-page flow, and `logout/` is unaffected by this change.

## 6. Security

- **Rate limiting** via `django-ratelimit` on `send-code`, `verify-code`, `login-password`, `register` — per-IP and per-email keys, e.g. `5/m` per IP and `3/m` per email on `send-code`, similar conservative limits on the others. Exact rates finalized during implementation/testing.
- **Honeypot**: one hidden field on the registration form (e.g. `middle_name`), positioned off-screen via CSS, never shown to sighted users. Non-empty value on submit → silently pretend success, don't create a user, don't reveal the check exists.
- **Cloudflare Turnstile**: invisible widget loaded on the modal, its token sent with `send-code` and `register` calls. Server-side verification against Cloudflare's siteverify endpoint before proceeding. Requires new settings `TURNSTILE_SITE_KEY` / `TURNSTILE_SECRET_KEY` (env vars) — **you'll need to create a free Turnstile site in your Cloudflare dashboard to get these**.

## 7. Frontend

- One modal component, visually based on the existing `.hp-modal-overlay`/`.hp-modal` pattern used for the homepage review modal (`templates/pages/home.html`, `staticfiles/css/pages/home.css:521-635`), reusing the same CSS custom properties (`--font-heading`, `--primary-color`, `--accent-color`, `--text-muted`, `--hp-border`, `--font-main`, `--text-main`) so it looks native to the site rather than bolted on.
- Internal steps swapped via vanilla JS (matching the existing no-framework, no-Bootstrap approach), no page reloads: email → (branch: password-or-code for existing users, or automatic code-send for new users) → code entry (6 boxes, "Didn't receive a code? Resend") → registration form (new users only) → success/redirect.
- Every "Book Now" link/button and the header "Login" link get a click-intercept: a small shared JS module checks a server-rendered `isAuthenticated` flag; if true, the link navigates normally; if false, `preventDefault()`, remember the link's `href` as the post-login redirect target, and open the modal.
- All new copy (labels, button text, error/help messages) added to `makemessages -l bg -l en` output and translated in `locale/bg/django.po` and `locale/en/django.po`, then `compilemessages`, per your CLAUDE.md rule.

## 8. Testing approach (for the implementation plan)

- `EmailOTP`: expiry, attempts cap, hashing (code never queryable in plaintext).
- `check-email/`: existing vs. non-existing email.
- `send-code/`: happy path emails a code (using Django's test email backend, not the real Gmail backend); rejected when rate limit exceeded; rejected when Turnstile verification fails (mocked).
- `verify-code/`: correct code logs in an existing user / advances a new user to registration; wrong code increments attempts and eventually invalidates the row; expired code rejected.
- `login-password/`: existing `CustomAuthenticationForm` behavior (including the inactive-user message) still works through the new endpoint.
- `register/`: creates an active, logged-in user with correct fields; rejects without a verified-email session; honeypot filled → fake success, no user row created; reuses the phone-number "claim" behavior correctly.
- End-to-end: Django test client walking through check-email → send-code → verify-code → register → redirect for a brand-new user, and check-email → login-password for an existing user.

## 9. Open items resolved during brainstorming (for reference)

- Modal opens immediately on "Book Now" click, before any service/professional/time selection (not after, as the reference screenshot's captured state might suggest).
- Modal fully replaces the old full-page login/register *everywhere* on the site, including the header "Login" link — not just the booking entry point.
- Google OAuth ("Continue with Google") deferred to a separate follow-up plan using `django-allauth`; omitted from the UI entirely in this plan (not shown disabled).
- Rate limiting via `django-ratelimit` (new dependency) rather than a hand-rolled cache-based limiter.
- Bot defense via Cloudflare Turnstile (new dependency/external service) rather than reCAPTCHA v3.
- Legacy `is_active=False` accounts are explicitly left unaddressed by this plan.

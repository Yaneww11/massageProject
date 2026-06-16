# B06 Missing Production Security Headers

**Severity:** HIGH
**File:** `massageProject/settings.py:60-69` (MIDDLEWARE block) / entire file
**Type:** Configuration / Transport Security

## Description

`settings.py` enables `django.middleware.security.SecurityMiddleware` at line 61 but configures none of its production security settings. The following settings are entirely absent from the file:

| Setting | Default | Risk |
|---|---|---|
| `SECURE_SSL_REDIRECT` | `False` | HTTP requests are never upgraded to HTTPS |
| `SECURE_HSTS_SECONDS` | `0` | No HSTS header sent; browsers won't enforce HTTPS |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | `False` | Subdomains remain vulnerable |
| `SESSION_COOKIE_SECURE` | `False` | Session cookie sent over plain HTTP |
| `CSRF_COOKIE_SECURE` | `False` | CSRF token sent over plain HTTP |
| `SECURE_CONTENT_TYPE_NOSNIFF` | `True` (since Django 3.0) | Acceptable, but should be explicit |
| `SECURE_BROWSER_XSS_FILTER` | removed in Django 4.0 | N/A |
| `X_FRAME_OPTIONS` | `'DENY'` | Already set via middleware, but not explicit |

The most critical omissions are `SESSION_COOKIE_SECURE` and `CSRF_COOKIE_SECURE`. When these are `False`, Django sends the session cookie and CSRF cookie without the `Secure` flag, meaning they are transmitted over unencrypted HTTP connections even when the site is accessible via HTTPS.

## Attack Scenario

**Session hijacking over HTTP (SESSION_COOKIE_SECURE missing):**

1. The production server is behind an nginx reverse proxy that accepts both HTTP (port 80) and HTTPS (port 443).
2. Because `SECURE_SSL_REDIRECT` is not set, Django itself does not redirect HTTP to HTTPS.
3. A user on a coffee-shop Wi-Fi visits `http://example.com/` instead of `https://example.com/`.
4. Django sets the `sessionid` cookie without the `Secure` flag.
5. An attacker performing a passive network sniff captures the `Set-Cookie: sessionid=...` response header.
6. The attacker replays the stolen session cookie and is authenticated as the victim with no credentials.

**CSRF over HTTP (CSRF_COOKIE_SECURE missing):**

1. Same network scenario as above.
2. The CSRF token is readable over HTTP, allowing an attacker-controlled page to read the token via a same-origin HTTP request and submit a forged cross-site POST to the HTTP endpoint.

**No HSTS (SECURE_HSTS_SECONDS missing):**

1. Even if nginx redirects port 80 to 443, browsers have no knowledge of this policy.
2. An SSL-strip attack downgrades the first request to HTTP before the redirect fires, capturing credentials or cookies.

## Fix Plan

Add the following block to `settings.py`, gated on `DEBUG` so local development is unaffected. Insert it after line 40 (`ALLOWED_HOSTS`):

```python
# Before: no security header settings exist

# After: add after line 40
if not DEBUG:
    # Force HTTPS
    SECURE_SSL_REDIRECT = True

    # HSTS: tell browsers to only use HTTPS for 1 year
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # Cookies must only be sent over HTTPS
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # Prevent MIME-type sniffing (explicit, even though Django 3+ defaults True)
    SECURE_CONTENT_TYPE_NOSNIFF = True

    # Prevent the site from being embedded in an iframe on other domains
    X_FRAME_OPTIONS = 'DENY'
```

If the project uses a reverse proxy (nginx/Apache) that terminates TLS, also add:

```python
    # Tell Django to trust the X-Forwarded-Proto header from the proxy
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
```

## Verification

1. Run Django's built-in deployment checklist — it checks all of these settings:
   ```bash
   DEBUG=False python manage.py check --deploy
   ```
   Before the fix: multiple `security.W` warnings are reported.
   After the fix: no security warnings.

2. With the server running behind HTTPS, use `curl -I http://example.com/` and confirm a `301` redirect to `https://`.

3. Inspect the `Set-Cookie` response header and confirm both `sessionid` and `csrftoken` carry the `Secure` flag:
   ```
   Set-Cookie: sessionid=...; HttpOnly; Secure; SameSite=Lax
   Set-Cookie: csrftoken=...; Secure; SameSite=Lax
   ```

4. Check the response headers for `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`.

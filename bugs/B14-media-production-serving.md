# B14 User-Uploaded Media Files Return 404 in Production

**Severity:** HIGH
**File:** `massageProject/urls.py:41-42`
**Type:** Configuration / Broken Functionality

## Description

`urls.py` appends Django's development media-serving URL only when `DEBUG` is `True`:

```python
# urls.py lines 41-42
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

Django's own documentation for `django.conf.urls.static.static()` states:

> "This helper function works only in debug mode and only if the given prefix is local (e.g. `/media/`) and not a URL (e.g. `http://media.example.com/`). In non-debug mode, this function returns an empty list."

When `DEBUG=False` (production), the `static()` call returns an empty list regardless, so no URL route handles `/media/` paths. Every user-uploaded file — masseur profile photos, gallery images, and any other content stored under `MEDIA_ROOT` — returns **HTTP 404**. This breaks:

- The home-page carousel (images from `HomePage.gallery`).
- The massages page (massage and masseur photos).
- The gallery page.
- Any admin-uploaded branding images (e.g. `media/branding/` seen in git status).

Additionally, even in development, Django's documentation explicitly warns that `static()` is "grossly inefficient and probably insecure" — it reads files directly in Python with no caching or range-request support.

## Attack Scenario

This is primarily a **broken-functionality bug** rather than an active security exploit, but it has a security-adjacent consequence:

1. The application is deployed to production with `DEBUG=False`.
2. All `<img src="/media/...">` tags render as broken images site-wide.
3. A staff member notices images are missing and temporarily sets `DEBUG=True` in production to "fix" it — inadvertently exposing detailed tracebacks, the full settings dump (including `SECRET_KEY`), and interactive debug consoles to the public internet.

Separately, serving media via Django's file views (even in dev) means uploaded files bypass the web server's access controls. A malicious user who uploads a file with a crafted filename could attempt path-traversal reads if the file-serving code has any flaw.

## Fix Plan

### Option A — nginx (recommended for most VPS/dedicated deployments)

Configure nginx to serve `/media/` directly from the filesystem, bypassing Django entirely. No change to `urls.py` is needed.

```nginx
# nginx site config
server {
    # ... existing HTTPS config ...

    location /media/ {
        alias /home/yaneyan/pycharmProjects/yane/massageProject/media/;
        # Deny direct execution of uploaded scripts
        location ~* \.(php|py|pl|sh)$ { deny all; }
    }
}
```

### Option B — WhiteNoise (simpler, single-process deployments)

Install WhiteNoise and configure it to serve both static and media files through Django itself. This is appropriate for Heroku-style deployments but still not recommended for high-traffic sites.

```bash
pip install whitenoise
```

In `settings.py`, insert `WhiteNoiseMiddleware` after `SecurityMiddleware` (line 61):

```python
# Before
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    ...
]

# After
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # <-- add this line
    'django.contrib.sessions.middleware.SessionMiddleware',
    ...
]
```

Note: WhiteNoise handles `STATIC_URL` natively but does **not** serve `MEDIA_URL` by default. A custom storage backend or explicit route is still required for media. The nginx approach (Option A) remains the correct solution for media files.

### Option C — Cloud storage (CDN deployments)

Move media uploads to an object store (AWS S3, Cloudflare R2, etc.) using `django-storages`. Files are served directly from the CDN; Django never handles media requests.

```bash
pip install django-storages boto3
```

```python
# settings.py — add when not DEBUG
if not DEBUG:
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    AWS_STORAGE_BUCKET_NAME = env('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_REGION_NAME = env('AWS_S3_REGION_NAME')
    MEDIA_URL = f'https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/'
```

## Verification

1. Set `DEBUG=False` in `.env` and restart the server.
2. Navigate to any page that displays an uploaded image (home page carousel, massages page).
3. **Before the fix:** all `<img>` tags referencing `/media/...` return 404 in the browser network tab.
4. **After the fix (nginx):** `curl -I http://localhost/media/<any-uploaded-file>` returns `200 OK` with the correct `Content-Type`.
5. Confirm Django itself receives no requests for `/media/` paths by checking Django's request log — nginx (or the CDN) should handle them entirely.

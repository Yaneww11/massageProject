# B09 Comment Endpoint Has No Rate Limiting

**Severity:** HIGH
**File:** `massageProject/main_app/views.py:264`
**Type:** Denial of Service / Abuse

## Description

The `submit_comment` view (lines 263–290 of `views.py`) accepts POST requests and persists a `Comment` row on every call. There is no IP-based throttling, no per-user cooldown, no CAPTCHA, and no request volume check of any kind. Although submitted comments are stored with `is_reviewed=False` and do not appear publicly until an admin approves them, the abuse surface is still real:

- The database `comment` table can be filled with millions of junk rows by a trivial script.
- The Django admin moderation queue becomes unusable when thousands of spam rows are queued.
- Bulk inserts of large-content rows (see B10) compound the storage and query-time impact.
- The endpoint is reachable by unauthenticated users, so no login is required to trigger the flood.

## Attack Scenario

1. Attacker sends a loop of POST requests to `/submit-comment/` (or whatever URL is mapped to `submit_comment`):
   ```bash
   while true; do
     curl -s -X POST https://example.com/submit-comment/ \
       -d "content=spam&author=Bot&rating=5"
   done
   ```
2. Each request passes all existing checks (non-empty `content`, valid `rating` clamp at line 268) and reaches `comment.save()` at line 289.
3. A single machine can create thousands of rows per minute; a distributed attack can create millions per hour.
4. The admin opens the moderation list and finds it overwhelmed; legitimate comments are buried or the page times out.

## Fix Plan

### Option A — Django's built-in cache-based throttle (simplest, no new dependency)

Add a per-IP cooldown in `submit_comment` before any DB work is done.

**Before (lines 263–275):**
```python
@require_POST
def submit_comment(request):
    content = request.POST.get('content', '').strip()
    author_name = request.POST.get('author', '').strip()
    try:
        rating = max(1, min(5, int(request.POST.get('rating', 5))))
    except (ValueError, TypeError):
        rating = 5

    if not content:
        return JsonResponse({'success': False, 'error': _('Въведете мнение')}, status=400)
```

**After:**
```python
from django.core.cache import cache

@require_POST
def submit_comment(request):
    # Rate limit: 1 comment per 60 seconds per IP
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
    ip = ip.split(',')[0].strip()
    cache_key = f'comment_rl_{ip}'
    if cache.get(cache_key):
        return JsonResponse({'success': False, 'error': _('Моля, изчакайте преди да изпратите нов коментар.')}, status=429)
    cache.set(cache_key, 1, timeout=60)

    content = request.POST.get('content', '').strip()
    author_name = request.POST.get('author', '').strip()
    try:
        rating = max(1, min(5, int(request.POST.get('rating', 5))))
    except (ValueError, TypeError):
        rating = 5

    if not content:
        return JsonResponse({'success': False, 'error': _('Въведете мнение')}, status=400)
```

This requires Django's cache backend to be configured (even the default `LocMemCache` works in development; use Redis or Memcached in production).

### Option B — django-ratelimit (cleaner decorator approach)

```bash
pip install django-ratelimit
```

```python
from ratelimit.decorators import ratelimit

@require_POST
@ratelimit(key='ip', rate='1/m', method='POST', block=True)
def submit_comment(request):
    ...
```

## Verification

1. Send 5 rapid POST requests to the endpoint from the same IP.
2. The second request (or whichever breaches the limit) must receive HTTP 429.
3. After the cooldown window passes, one more request must succeed (HTTP 200 with `success: true`).
4. Confirm the `comment` table row count did not grow beyond 1 during the burst.

# B12 Unauthenticated Comment Author Field Accepts Arbitrary Display Names

**Severity:** MEDIUM
**File:** `massageProject/main_app/views.py:286`
**Type:** Input Validation / Content Integrity

## Description

In `submit_comment` (lines 263–290 of `views.py`), when the submitting user is not authenticated, the `author` display name is taken verbatim from the POST body:

```python
# views.py lines 286–287
elif author_name:
    comment.author = author_name
```

`author_name` is read directly from POST at line 266:

```python
author_name = request.POST.get('author', '').strip()
```

There is no validation beyond `.strip()`. The `Comment.author` field (model line 398–402) is a `CharField(max_length=100, null=True, blank=True)` — it stores whatever string is provided.

The only protection is that `is_reviewed=False` means an admin must approve the comment before it appears publicly. However, this still creates two concrete problems:

1. **Admin deception:** A spam or defamatory comment submitted as `author="Управителят"` ("The Manager") or `author="Dr. Expert"` carries false authority in the moderation queue. An admin working quickly may approve it without scrutinising the author field.
2. **Impersonation of real users:** A logged-in user's display name is set from `user.get_full_name()` (line 279). An unauthenticated attacker who knows a real customer's name can post comments that appear to come from that person once approved.

The `AboutPage.post` handler has the same issue at lines 247–251, where an unauthenticated POST similarly writes `form`-provided author data straight to `comment.author` (though that path goes through `CommentForm`, which may have a validator — `submit_comment` does not use a form at all).

## Attack Scenario

1. Attacker inspects the page source or network tab to find the `submit_comment` POST endpoint and its expected parameters.
2. Attacker sends:
   ```bash
   curl -X POST https://example.com/submit-comment/ \
     -d "content=Отличен масаж, препоръчвам!&author=Иван Иванов&rating=5"
   ```
   where "Иван Иванов" is the real name of a known client (e.g. inferred from a visible approved comment).
3. The comment is stored with `author="Иван Иванов"` and `is_reviewed=False`.
4. Admin reviews the queue, sees a glowing 5-star comment from what looks like a regular client, and approves it.
5. A fake positive review attributed to a real person (or a fake negative review attributed to a competitor's name) is now live on the site.

## Fix Plan
### Require authentication to submit comments (strongest fix)

If business requirements allow it, restricting `submit_comment` to authenticated users eliminates the spoofing vector entirely. The author is then always derived from `user.get_full_name()` (line 279), which comes from the verified account record.

**`views.py` — add `@login_required` decorator above `@require_POST`:**

**Before (lines 261–264):**
```python
from django.views.decorators.http import require_POST

@require_POST
def submit_comment(request):
```

**After:**
```python
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

@login_required
@require_POST
def submit_comment(request):
```

With this change, the `elif author_name:` branch (lines 286–287) becomes unreachable and can be removed.

## Verification

1. Without fixing: send a POST with `author="Studio Manager"` and confirm the row in the DB has `author="Studio Manager"` and `user_id=NULL`.
2. After applying Option A: send the same POST — must receive HTTP 400 with `"Невалидно име."`.
3. After applying Option A: send a POST with `author="Иван Петров"` (plain Cyrillic name) — must succeed and create the row.
4. After applying Option B: send the POST without a session cookie — must receive HTTP 302 redirect to the login page (or HTTP 403 if AJAX).

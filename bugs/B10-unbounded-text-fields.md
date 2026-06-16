# B10 Unbounded TextField on Comment and Reservation Allows Oversized Payloads

**Severity:** MEDIUM
**File:** `massageProject/main_app/models.py:404` (Comment.content), `massageProject/main_app/models.py:145` (MessageReservation.additional_text)
**Type:** Input Validation / Resource Exhaustion

## Description

Two model fields accept arbitrarily large text with no enforced upper bound:

- **`Comment.content`** — defined at line 404 as `models.TextField()` with no `max_length`.
- **`MessageReservation.additional_text`** — defined at line 145 as `models.TextField(default='', blank=True)` with no `max_length`.

In PostgreSQL, `TEXT` columns have no hard size cap (theoretical max ~1 GB per value). Nothing in either model's `clean()` method, nor in the `submit_comment` view (lines 263–290), enforces a content length check. The `submit_comment` view reads the raw POST body field directly:

```python
# views.py line 265
content = request.POST.get('content', '').strip()
```

and saves it without any length validation:

```python
# views.py line 275
comment = Comment(content=content, rating=rating, is_reviewed=False)
```

Django's `DATA_UPLOAD_MAX_MEMORY_SIZE` setting (default 2.5 MB) limits the total POST body, but a single field can still fill that entire budget. For unauthenticated users this is completely open; for authenticated users the same limit applies to `additional_text` on reservations.

### Consequences

- **Storage waste:** A single submission can write megabytes of garbage into the DB.
- **Admin slowdown:** The Django admin comment list renders the full content column; very long values cause page rendering to hang or time out.
- **Combined with B09 (no rate limit):** A burst of large-payload requests can fill gigabytes of disk quickly.

## Attack Scenario

1. Attacker crafts a POST body with a `content` value of ~2 MB of random text (just under Django's default body-size limit).
2. Each request creates a `Comment` row storing ~2 MB in the `content` column.
3. At even 100 requests per minute (well within a single machine's capacity), that is 200 MB of junk per minute in the database.
4. The admin opens the moderation queue to review pending comments; the page either times out or is extremely slow due to fetching and rendering multi-megabyte text cells.

## Fix Plan

### 1. Add `max_length` validation to both model fields

Django `TextField` does not enforce `max_length` at the database level, but it does enforce it during `full_clean()` / form validation when `max_length` is set.

**`models.py` line 404 — before:**
```python
content = models.TextField()
```

**After:**
```python
content = models.TextField(max_length=2000)
```

**`models.py` line 145 — before:**
```python
additional_text = models.TextField(default='', blank=True)
```

**After:**
```python
additional_text = models.TextField(default='', blank=True, max_length=500)
```

### 2. Add an explicit length guard in `submit_comment` (defense in depth)

Because `submit_comment` constructs the `Comment` object directly and calls `save()` without going through a `ModelForm`, the `max_length` set on the model field is not automatically checked. Add a manual check in the view before the object is constructed.

**`views.py` — insert after line 273 (the empty-content check):**

**Before:**
```python
    if not content:
        return JsonResponse({'success': False, 'error': _('Въведете мнение')}, status=400)

    comment = Comment(content=content, rating=rating, is_reviewed=False)
```

**After:**
```python
    if not content:
        return JsonResponse({'success': False, 'error': _('Въведете мнение')}, status=400)

    if len(content) > 2000:
        return JsonResponse({'success': False, 'error': _('Мнението не може да надвишава 2000 символа.')}, status=400)

    comment = Comment(content=content, rating=rating, is_reviewed=False)
```

### 3. Create a migration

After changing the model fields, generate and apply a migration:

```bash
source venv/bin/activate
python manage.py makemigrations main_app
python manage.py migrate
```

Note: adding `max_length` to an existing `TextField` in PostgreSQL does not alter the column type — it only adds a check constraint. No table lock or data rewrite is needed.

## Verification

1. Submit a POST to `submit_comment` with a `content` value longer than 2000 characters.
2. The response must be HTTP 400 with the length error message.
3. Confirm no `Comment` row was inserted.
4. Submit a valid comment (under 2000 characters) and confirm it is saved normally.
5. Attempt to save a `MessageReservation` with `additional_text` longer than 500 characters via a form and confirm `ValidationError` is raised.

# B08 Missing 404 Handlers — Unhandled DoesNotExist Raises HTTP 500

**Severity:** HIGH
**File:** `massageProject/main_app/views.py:348,353,383`
**Type:** Error Handling / Information Disclosure

## Description

Three places in `views.py` call `ModelName.objects.get(pk=pk)` with no try/except and
no use of `get_object_or_404()`. When a user (or an attacker) supplies a PK that does
not exist — or supplies the PK of a soft-deleted record, which the default manager
intentionally excludes — Django raises `Model.DoesNotExist`. Because nothing catches it,
Django propagates the exception as an HTTP 500 Internal Server Error.

This has two consequences:

1. **User experience:** A legitimate user who clicks a stale link or manually edits a
   URL sees a generic server-error page instead of a clean "not found" page.
2. **Information disclosure:** With `DEBUG=True` (common in development, sometimes
   accidentally left on) the 500 page leaks a full Django traceback including ORM
   queries, local variables, and file paths. Even with `DEBUG=False` the 500 response
   can be logged in monitoring systems and may trigger alerts, adding noise.

### Affected locations

| Line | Code |
|------|------|
| 348 | `MassageDetail.get` — `Massage.objects.get(pk=kwargs['pk'])` |
| 353 | `edit_reservation` — `MessageReservation.objects.get(pk=pk)` |
| 383 | `delete_reservation` — `MessageReservation.objects.get(pk=pk)` |

Note: `get_object_or_404` is already imported on line 1 and is used correctly in
`GalleryAlbumView` (line 429), so the pattern is established — it just was not applied
consistently.

## Attack Scenario

1. Attacker visits any massage detail URL, e.g. `/massages/9999/`.
2. `MassageDetail.get` calls `Massage.objects.get(pk=9999)` (line 348); no such massage
   exists.
3. Django raises `Massage.DoesNotExist`; the view has no handler.
4. Django returns HTTP 500 with a traceback (if `DEBUG=True`) or a generic 500 page.
5. The same happens for `/reservations/edit/9999/` and `/reservations/delete/9999/` for
   a non-existent or soft-deleted reservation PK.
6. An attacker can use this to confirm which PKs exist (200/403) versus which do not
   (500), treating the error as an oracle.

## Fix Plan

Replace all three bare `.get()` calls with `get_object_or_404()`. No import change is
needed — `get_object_or_404` is already imported on line 1.

### Fix 1 — `MassageDetail.get` (line 348)

**Before:**
```python
context['massage'] = Massage.objects.get(pk=kwargs['pk'])
```

**After:**
```python
context['massage'] = get_object_or_404(Massage, pk=kwargs['pk'])
```

### Fix 2 — `edit_reservation` (line 353)

**Before:**
```python
def edit_reservation(request, pk: int):
    reservation = MessageReservation.objects.get(pk=pk)
```

**After:**
```python
def edit_reservation(request, pk: int):
    reservation = get_object_or_404(MessageReservation, pk=pk)
```

### Fix 3 — `delete_reservation` (line 383)

**Before:**
```python
def delete_reservation(request, pk: int):
    reservation = MessageReservation.objects.get(pk=pk)
```

**After:**
```python
def delete_reservation(request, pk: int):
    reservation = get_object_or_404(MessageReservation, pk=pk)
```

All three fixes are one-line, drop-in replacements. The ownership check and 24-hour rule
that follow each `.get()` call are unaffected.

## Verification

1. Start the dev server: `python manage.py runserver`.
2. Navigate to a non-existent massage detail URL, e.g. `http://localhost:8000/massages/99999/`.
3. **Before fix:** HTTP 500 response (traceback visible if `DEBUG=True`).
4. **After fix:** HTTP 404 response with the standard "Page not found" page.
5. Repeat for `/reservations/edit/99999/` and `/reservations/delete/99999/` while
   logged in as any user.

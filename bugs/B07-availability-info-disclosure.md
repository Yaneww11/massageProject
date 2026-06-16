# B07 Availability Endpoint Information Disclosure

**Severity:** MEDIUM
**File:** `massageProject/main_app/views.py:20`
**Type:** Authentication / Information Disclosure

## Description

The `check_availability` view (lines 20–90) has no `@login_required` decorator and no
authentication check of any kind. It is a fully public GET endpoint reachable at:

```
/check-availability/?masseur_id=X&date=YYYY-MM-DD&massage_id=Y
```

The response includes a slot list where every entry has `"available": false` and
`"reason": "taken"` for slots that are already booked. This lets any unauthenticated
visitor — or an automated script — enumerate the booking schedule of every therapist
across any date range, revealing:

- Which time slots are occupied (and therefore how many clients visit per day).
- Overall business volume and peak hours.
- Therapist-specific availability patterns over time.

No account, login, or session cookie is required.

## Attack Scenario

1. Attacker discovers (or guesses) the endpoint from the browser's network tab while
   browsing the public reservation page.
2. Attacker writes a simple loop over all masseur IDs (small integers), all dates in a
   range, and each massage type ID.
3. For every combination the response returns a full 30-minute slot grid with `"taken"`
   markers.
4. Attacker builds a complete occupancy map of the studio: which therapists are busiest,
   which days are fully booked, and — by inference — rough client-visit frequency.
5. The data can be collected indefinitely with no authentication, rate-limiting, or
   detection.

## Fix Plan

Add `@login_required` immediately above the function definition (line 20). The decorator
is already imported on line 5 and is used elsewhere in the file (lines 351, 381), so no
new import is needed.

**Before (line 20):**
```python
def check_availability(request):
```

**After:**
```python
@login_required
def check_availability(request):
```

If the endpoint must remain partially public (e.g. to let anonymous visitors browse
available slots before deciding to register), the minimum acceptable alternative is to
return only `"available": true/false` without the `"reason"` field, so that booked slots
cannot be distinguished from non-working hours by an unauthenticated caller:

```python
slots.append({
    'time': slot_time.strftime('%H:%M'),
    'available': is_available,
    # omit 'reason' for unauthenticated requests
})
```

The stronger fix — `@login_required` — is preferred because the reservation page
(`ReservationPage`, line 124) already requires login, so the JS that calls this endpoint
only ever runs for authenticated users anyway.

## Verification

1. Log out of the application.
2. Send a request directly to the endpoint:
   ```
   curl -s "http://localhost:8000/check-availability/?masseur_id=1&date=2026-06-20&massage_id=1"
   ```
3. **Before fix:** response is `200 OK` with a slot list.
4. **After fix:** response is `302 Found` redirecting to the login page (or `403` if
   `raise_exception=True` is passed to the decorator).

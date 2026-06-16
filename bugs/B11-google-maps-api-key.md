# B11 Google Maps API Key Is a Hardcoded Placeholder

**Severity:** HIGH
**File:** `templates/pages/home.html:268`
**Type:** Configuration / Credential Exposure

## Description

Line 268 of `templates/pages/home.html` loads the Google Maps JavaScript API with a literal placeholder string instead of a real key:

```html
<script async defer src="https://maps.googleapis.com/maps/api/js?key=YOUR_API_KEY_HERE&callback=initMap"></script>
```

This causes two distinct problems:

1. **The map never loads.** Google rejects the request because `YOUR_API_KEY_HERE` is not a valid API key. Every visitor sees a broken map section on the homepage.
2. **Future secret exposure risk.** If a developer fixes this by pasting a real API key directly into the template, that key will be committed to version control and visible in the repository's history indefinitely — even after a later removal. Anyone with read access to the repo can steal the key and run up billing charges.

## Attack Scenario

**For the broken-map issue (current state):**
1. Visitor opens the homepage.
2. The browser requests `https://maps.googleapis.com/maps/api/js?key=YOUR_API_KEY_HERE&callback=initMap`.
3. Google returns an error response; `initMap` is never called or fails silently.
4. The map section renders as a blank or broken element.

**For the credential-exposure risk (future state if naively fixed):**
1. Developer replaces `YOUR_API_KEY_HERE` with a real key directly in the template.
2. Developer commits and pushes the file.
3. Attacker clones or browses the repository, finds the key in `git log -p` or directly in the file.
4. Attacker uses the key to make geocoding/Maps API calls billed to the studio's Google Cloud account, or abuses quota to cause denial-of-service against the maps feature.

## Fix Plan

**Step 1 — Add `GOOGLE_MAPS_API_KEY` to the `.env` file and to `settings.py`.**

In `massageProject/settings.py`, after the existing `environ` setup (around line 28), add:

```python
# Before (nothing exists for Maps key)

# After — add this line:
GOOGLE_MAPS_API_KEY = env('GOOGLE_MAPS_API_KEY', default='')
```

**Step 2 — Expose the key to templates via the existing context processor or a new one.**

The project already has a context processor at `massageProject/main_app/context_processors.py` (`admin_branding` is registered in `settings.py` line 85). Add the Maps key there so it is available in every template automatically, or pass it from the view that renders the homepage.

Option A — add to the existing context processor (minimal change):

```python
# massageProject/main_app/context_processors.py
from django.conf import settings

def admin_branding(request):
    # ... existing code ...
    return {
        # ... existing keys ...
        'GOOGLE_MAPS_API_KEY': settings.GOOGLE_MAPS_API_KEY,
    }
```

**Step 3 — Replace the hardcoded placeholder in the template.**

`templates/pages/home.html`, line 268:

```html
<!-- Before -->
<script async defer src="https://maps.googleapis.com/maps/api/js?key=YOUR_API_KEY_HERE&callback=initMap"></script>

<!-- After -->
<script async defer src="https://maps.googleapis.com/maps/api/js?key={{ GOOGLE_MAPS_API_KEY }}&callback=initMap"></script>
```

**Step 4 — Add `GOOGLE_MAPS_API_KEY` to `.env` (and `.env.example` if one exists).**

```
GOOGLE_MAPS_API_KEY=AIza...your_real_key...
```

Ensure `.env` is listed in `.gitignore` (it already is based on the current git status showing `.gitignore` modified).

## Verification

1. Set a valid `GOOGLE_MAPS_API_KEY` in `.env` and restart the dev server.
2. Open the homepage in a browser and inspect the network tab — the Maps JS request should return HTTP 200.
3. The map section should render correctly with the studio location marker.
4. Run `grep -r "YOUR_API_KEY_HERE" templates/` — should return no results.
5. Run `grep -r "AIza" templates/` — should return no results (key must not be in templates).

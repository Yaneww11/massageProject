# B13 Rosetta Translation Editor Lacks Explicit Access Control

**Severity:** MEDIUM
**File:** `massageProject/urls.py:31`
**Type:** Authentication / Authorization

## Description

`massageProject/urls.py` mounts the Rosetta translation editor unconditionally:

```python
# massageProject/urls.py, line 31
path('rosetta/', include('rosetta.urls')),
```

This route sits **outside** the `i18n_patterns` block (lines 34–39) and carries no access guard of its own. Rosetta's built-in default requires `is_staff=True`, but this is enforced inside Rosetta's own views — not in the URL configuration. That means:

- The setting `ROSETTA_ACCESS_CONTROL_FUNCTION` is absent from `settings.py`, so the project relies entirely on Rosetta's undocumented default behaviour.
- If Rosetta is upgraded or misconfigured, a version whose default changes could expose the editor to any authenticated (or even unauthenticated) user.
- There is no defence-in-depth: a single library behaviour is the only gate on a tool that can rewrite every user-facing string in the application.
- The `/rosetta/` path is also accessible in production (there is no `if settings.DEBUG` guard), unlike the media-file serving on line 41–42.

## Attack Scenario

**Current risk (library default relied upon):**
1. Attacker registers a normal user account on the site (public registration is available at `/accounts/`).
2. Attacker navigates to `/rosetta/` (or `/en/rosetta/`, `/bg/rosetta/` if Rosetta respects the i18n prefix).
3. If Rosetta's `is_staff` check is bypassed — e.g. through a Rosetta bug, a future version change, or a misconfigured `ROSETTA_ACCESS_CONTROL_FUNCTION` — the attacker reaches the translation editor.
4. Attacker modifies UI strings: replaces button labels, error messages, or form field labels with phishing text or malicious URLs, affecting all visitors without touching any template file.

**Privilege escalation via string injection:**
1. Attacker with editor access changes the "Forgot password" link label to point to an attacker-controlled domain.
2. Real users click the manipulated link and submit credentials to the attacker's server.

## Fix Plan

**Step 1 — Set `ROSETTA_ACCESS_CONTROL_FUNCTION` in `settings.py` to make the restriction explicit and version-safe.**

Add after the `INSTALLED_APPS` block (after line 58 in `massageProject/settings.py`):

```python
# Before (nothing — relies on Rosetta's internal default)

# After — add this block:
def _rosetta_staff_only(user):
    return user.is_active and user.is_staff

ROSETTA_ACCESS_CONTROL_FUNCTION = 'massageProject.settings._rosetta_staff_only'
```

Alternatively, define the function in a dedicated module (e.g. `massageProject/utils.py`) and reference it there to avoid putting a function in `settings.py`.

**Step 2 — Guard the URL pattern itself so it is only mounted in DEBUG or only when the user is staff (defence-in-depth).**

Option A — restrict to DEBUG (simplest, keeps Rosetta off in production entirely):

`massageProject/urls.py`, replace lines 29–32:

```python
# Before
urlpatterns = [
    path('i18n/', include(i18n_urls)),
    path('rosetta/', include('rosetta.urls')),
]

# After
urlpatterns = [
    path('i18n/', include(i18n_urls)),
]

if settings.DEBUG:
    urlpatterns += [
        path('rosetta/', include('rosetta.urls')),
    ]
```

Option B — keep Rosetta available in production but make the intent explicit by adding both the URL guard (Step 2A) and the `ROSETTA_ACCESS_CONTROL_FUNCTION` (Step 1). This is the safer combination if production translation editing is genuinely needed.

## Verification

1. Log in as a non-staff user and navigate to `/rosetta/` — expect a 403 or redirect to login.
2. Log in as a staff user and navigate to `/rosetta/` — expect the translation editor to load normally.
3. If using the DEBUG-only guard: set `DEBUG=False` in `.env`, restart the server, and confirm `/rosetta/` returns 404.
4. Run `grep -r "ROSETTA_ACCESS_CONTROL_FUNCTION" massageProject/settings.py` — should return the newly added line.

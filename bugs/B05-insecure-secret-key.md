# B05 Insecure Secret Key in Production

**Severity:** CRITICAL
**File:** `massageProject/settings.py:35`
**Type:** Configuration / Cryptographic Weakness

## Description

`SECRET_KEY` is loaded from the `.env` file at line 35:

```python
SECRET_KEY = env('SECRET_KEY')
```

Django's `startproject` command generates placeholder keys prefixed with `django-insecure-` to signal that the key was auto-generated and is not safe for production use. If the `.env` file contains a key that starts with `django-insecure-`, deploying with it means:

- Session cookies are signed with a publicly known or trivially guessable key.
- CSRF tokens can be forged.
- Any Django component that uses `SECRET_KEY` for signing (password reset tokens, `signing.dumps/loads`, `{% url %}` signed URLs) is compromised.
- An attacker who knows the key (e.g. from a leaked `.env` or from the fact that the default key is often committed to version control) can sign arbitrary session data, effectively bypassing authentication for any account including superusers.

Django itself warns about this at startup when `DEBUG=False` and the key carries the `django-insecure-` prefix.

## Attack Scenario

1. Developer runs `django-admin startproject`, commits the generated `.env` (or a `.env.example`) to a public or semi-public repository. The generated `SECRET_KEY` begins with `django-insecure-`.
2. The same key is copied to the production `.env` file.
3. An attacker finds the key in Git history, a leaked backup, or by recognising the well-known prefix pattern.
4. The attacker crafts a signed session cookie for `user_id=1` (the superuser) using Django's signing utilities and the known key:
   ```python
   from django.core import signing
   # Using the leaked key directly
   value = signing.dumps({'_auth_user_id': '1', '_auth_user_backend': '...', '_auth_user_hash': '...'}, key='django-insecure-...')
   ```
5. The attacker sends this cookie to the application and is logged in as the superuser with no credentials required.

## Fix Plan

**Step 1 — Generate a strong secret key** (never commit it):

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

The output will **not** carry the `django-insecure-` prefix.

**Step 2 — Replace the value in `.env`:**

```
# Before (insecure — do NOT use in production)
SECRET_KEY=django-insecure-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# After
SECRET_KEY=<output from step 1>
```

**Step 3 — Add a startup guard in `settings.py`** after line 35 to prevent accidental deployment of an insecure key:

```python
# Before (line 35)
SECRET_KEY = env('SECRET_KEY')

# After
SECRET_KEY = env('SECRET_KEY')

if not DEBUG and SECRET_KEY.startswith('django-insecure-'):
    raise RuntimeError(
        "SECRET_KEY starts with 'django-insecure-'. "
        "Generate a secure key before deploying to production."
    )
```

**Step 4 — Ensure `.env` is in `.gitignore`** (already present according to git status, but confirm the actual secret value has never been committed):

```bash
git log --all --full-history -- .env
git grep 'django-insecure-'
```

If the key appears in history, rotate it immediately after deploying the fix.

## Verification

1. Set `DEBUG=False` in `.env` and attempt to start the server with the old insecure key — the `RuntimeError` guard should abort startup.
2. Replace the key with a freshly generated one — the server should start cleanly.
3. Confirm `python manage.py check --deploy` reports no `security.W009` warning about the insecure key prefix.

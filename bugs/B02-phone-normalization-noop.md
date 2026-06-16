# B02 Phone Normalization No-Op Allows Duplicate Accounts

**Severity:** HIGH
**File:** `massageProject/accounts/managers.py:71`
**Type:** Configuration

## Description

`AppUserManager.normalize_phone_number()` calls `phone_number.strip()` on line 71 but discards the return value. Python strings are immutable — `str.strip()` returns a *new* string with leading/trailing whitespace removed; it does not mutate the original. Because the result is never assigned back, `phone_number` still holds the original value (whitespace included) for the rest of the method.

```python
def normalize_phone_number(self, phone_number):
    phone_number.strip()          # result discarded — no-op
    if phone_number.startswith("+359"):
        phone_number = phone_number.replace("+359", "0")
    return phone_number
```

Consequences:

- `" 0899123456"` (leading space) and `"0899123456"` are treated as distinct values throughout the system. The `phone_number` column's unique constraint therefore permits both rows to coexist.
- A user who registers with accidental whitespace (copy-paste from a messaging app, auto-fill, etc.) cannot log in with the clean number, and vice versa.
- The same physical phone number can accumulate multiple accounts, each with its own reservations and credentials. This undermines the business rule that one phone = one account.
- The `+359`-to-`0` conversion that follows on line 72 also fails silently for padded input: `" +3598912345"` does not start with `"+359"` so the prefix substitution is skipped, producing `" +3598912345"` as the stored value.

## Attack Scenario

This is primarily an integrity/reliability bug rather than a direct attack vector, but it can be exploited:

1. A user registers with phone `0899123456`. Account A is created.
2. An attacker (or the same user by accident) registers with `" 0899123456"` (leading space). Because normalization is a no-op, `strip()` leaves the space in place, the unique constraint sees a different value, and Account B is created successfully.
3. Both accounts now exist. If the application uses `phone_number__iexact` lookups (as in `clean_phone_number()`), the lookup may match either account depending on which normalization path was taken, causing unpredictable authentication behavior.
4. More deliberately: an attacker who already has account A can register `" 0899123456"` to create a second account with identical contact details but a different password, effectively cloning the identity.

## Fix Plan

Assign the result of `strip()` back to `phone_number` on line 71.

Before (`managers.py` lines 70–74):

```python
def normalize_phone_number(self, phone_number):
    phone_number.strip()
    if phone_number.startswith("+359"):
        phone_number = phone_number.replace("+359", "0")
    return phone_number
```

After:

```python
def normalize_phone_number(self, phone_number):
    phone_number = phone_number.strip()
    if phone_number.startswith("+359"):
        phone_number = phone_number.replace("+359", "0")
    return phone_number
```

The only change is `phone_number = phone_number.strip()` (assignment added). No logic restructuring is needed.

After applying the fix, audit whether any existing rows in the `accounts_customuser` table contain phone numbers with leading or trailing whitespace, and normalise them:

```python
from django.contrib.auth import get_user_model
User = get_user_model()
for user in User.objects.all():
    stripped = user.phone_number.strip()
    if stripped != user.phone_number:
        user.phone_number = stripped
        user.save(update_fields=['phone_number'])
```

Run this as a one-off management command or data migration before deploying the fix, so the unique constraint is not violated on future lookups.

## Verification

Unit-test the manager method directly:

```python
from django.test import TestCase
from django.contrib.auth import get_user_model

class NormalizePhoneNumberTest(TestCase):
    def setUp(self):
        self.manager = get_user_model().objects

    def test_strips_leading_whitespace(self):
        self.assertEqual(self.manager.normalize_phone_number(' 0899123456'), '0899123456')

    def test_strips_trailing_whitespace(self):
        self.assertEqual(self.manager.normalize_phone_number('0899123456 '), '0899123456')

    def test_strips_and_converts_plus359(self):
        self.assertEqual(self.manager.normalize_phone_number(' +3598912345'), '08912345')

    def test_no_whitespace_unchanged(self):
        self.assertEqual(self.manager.normalize_phone_number('0899123456'), '0899123456')
```

Before the fix, `test_strips_leading_whitespace` returns `' 0899123456'` (space preserved) and fails. After the fix, all four tests pass.

# B01 Account Takeover via Passwordless User Hijacking

**Severity:** CRITICAL
**File:** `massageProject/accounts/forms.py:72`
**Type:** Authentication

## Description

`CustomUserForm.clean_phone_number()` contains a "claim passwordless account" shortcut: if a user with the submitted phone number already exists and `has_usable_password()` returns `False`, the method silently replaces `self.instance` with that existing user object (line 72). Django's `ModelForm` then treats the save as an *update* of that existing record rather than an insert of a new one.

The intent is presumably to allow accounts pre-created by staff (e.g., via social-login or an import) to be "claimed" by the real owner when they first register. The flaw is that there is **no second factor** tying the registrant to the pre-existing account. Any person who knows (or guesses) a phone number associated with a passwordless account can register with that number, choose their own password, and take ownership of the account — including any reservations, permissions, or personal data attached to it.

Because registration succeeds and the user is auto-logged-in afterward, the attacker immediately has an authenticated session as the victim.

## Attack Scenario

1. Attacker discovers (or guesses) that phone number `0899123456` belongs to an existing account that has no usable password (e.g., a staff-created placeholder account, a social-auth account, or an account whose password was intentionally unset).
2. Attacker navigates to `/register/` and fills in the form with `0899123456` and a password of their choosing.
3. `clean_phone_number()` finds the existing user, sees `has_usable_password() == False`, and sets `self.instance = existing_user` (line 72).
4. `UserCreationForm.save()` calls `self.instance.save()`, which updates the existing user record: the attacker's chosen password hash is written, and `first_name`, `last_name`, `email` are overwritten.
5. The view logs the attacker in as the existing user. The attacker now controls the account.

No email confirmation, no SMS OTP, no token — just knowledge of the phone number.

## Fix Plan

The root cause is that phone number alone is insufficient proof of ownership. The `self.instance` swap must either be removed entirely or gated behind a verified out-of-band confirmation (OTP sent to the phone).

**Minimal safe fix — remove the account-takeover path entirely.**

If the "claim passwordless account" feature is not actively needed, delete the `else` branch and treat a duplicate phone number as a hard error regardless of password status:

Before (`forms.py` lines 64–74):

```python
try:
    existing_user = User.objects.get(phone_number__iexact=normalized_phone)
    if existing_user.has_usable_password():
        raise ValidationError(self.error_messages["already_registered"])
    else:
        # Set the existing user as the instance for this form.
        # This allows ModelForm to update the existing record instead of creating a new one,
        # and it bypasses the unique constraint validation for this specific record.
        self.instance = existing_user
except User.DoesNotExist:
    pass
```

After:

```python
try:
    User.objects.get(phone_number__iexact=normalized_phone)
    raise ValidationError(self.error_messages["already_registered"])
except User.DoesNotExist:
    pass
```

**If the claim feature must be preserved**, it requires an out-of-band ownership proof before `self.instance` is ever replaced:

1. On form submission with a passwordless-account phone number, generate a short-lived signed token (e.g., `django.core.signing`) and send an SMS OTP to that number.
2. Redirect the user to a confirmation step where they enter the OTP.
3. Only after OTP validation, load the existing user and allow the password update.

Never replace `self.instance` based solely on a phone number that was typed into a form field.

## Verification

1. Create a test user with `set_unusable_password()`:
   ```python
   user = CustomUser.objects.create(phone_number='0899123456', first_name='Victim', ...)
   user.set_unusable_password()
   user.save()
   ```
2. Submit the registration form with phone `0899123456` and a new password.
3. **Before fix:** registration succeeds, the attacker is logged in as the victim user (`request.user.pk == victim.pk`).
4. **After fix:** `clean_phone_number()` raises `ValidationError` with the `already_registered` message; no session is created.

Add a regression test in `accounts/tests.py`:

```python
def test_registration_cannot_claim_passwordless_account(self):
    victim = CustomUser.objects.create(phone_number='0899123456', first_name='V', last_name='V')
    victim.set_unusable_password()
    victim.save()
    response = self.client.post('/register/', {
        'phone_number': '0899123456',
        'first_name': 'Attacker',
        'last_name': 'Attacker',
        'password1': 'StrongPass123!',
        'password2': 'StrongPass123!',
    })
    # Must not be logged in as victim
    self.assertNotEqual(self.client.session.get('_auth_user_id'), str(victim.pk))
```

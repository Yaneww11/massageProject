# Email polish — professional look + provider optimisation

Status: agreed, not yet implemented.

## Root cause being fixed

Transactional emails render inside the *triggering* request. When the photographer
(session = EN) uploads a gallery, `render_to_string` and `reverse('photo_proofing')`
both resolve under EN — so the client got an English subject, an English button, a
Bulgarian paragraph (missing EN catalog entry) and an `/en/` link.

## Decisions

| # | Decision |
|---|---|
| D1 | All transactional email renders in **`bg`**, always. Wrap the whole send in `translation.override('bg')` so subject, text body, HTML body and `reverse()` agree. No `language` field on `CustomUser`. |
| D2 | Fix `&amp;` in **`HomePage.brand_name_plain`** (`models.py:991`) with `html.unescape()` after `strip_tags`. Fixes email, logo alt, footer copyright and `ics.py` at once. |
| D3 | Scope = the **5 HTML emails**: gallery_ready, marks_finalized, final_delivery, otp, password_reset. |
| D4 | `marks_finalized_email` (goes to the specialist) follows the same `bg` rule. |
| D5 | Verify with **both** Django tests (language / link prefix / escaping) and a real Gmail send. |
| D6 | Email stays **light**: white content card, dark header band drawn from theme. No dark-background email. |
| D7 | Exactly **3 colors** from `SiteConfiguration`: `background_color` (header band + button bg), `primary_color` (header + button text), `accent_color` (links, hairline divider). Body text fixed `#1A1A1A` on `#FFFFFF` — `text_color` is a light colour meant for a dark page and would be invisible on the card. Footer uses a fixed grey, not a 4th field. |
| D8 | Three new `SiteConfiguration` fields, own "Имейли" fieldset: `email_logo`, `email_reply_to`, `email_signature`. Nothing else becomes admin-editable. |
| D9 | Footer renders `BusinessInfo.address` + `phone` + `email_address`. No social icons (images block by default, add weight). |
| D10 | **No** `List-Unsubscribe` — all five are strictly transactional. |
| D11 | Add **`SITE_URL`** setting; email functions build absolute links from it and **drop the `request` argument** entirely. 3 call sites: `views.py:762`, `views.py:895`, `views.py:1355`. |
| D12 | New subject lines (BG): see table below. |
| D13 | **No preheader text.** (User overrode the recommendation.) |
| D14 | `<meta name="color-scheme" content="light">` + `supported-color-schemes`. Accept that Gmail still inverts the dark header band to dark grey. |
| D15 | `email_logo` when set, text brand name when not. Max 160px wide, explicit `width`/`height`, real `alt` for blocked-image clients. |
| D16 | Password reset: wrap `BrandedPasswordResetView.form_valid` in `override('bg')`. Leave its duplicated brand lookup alone (pre-existing; surgical-changes rule). |

## Subject lines

| Email | Now | New |
|---|---|---|
| gallery ready | Вашата галерия за преглед е готова | Снимките ви са готови за преглед |
| final delivery | Финалните ви снимки са готови | Финалните ви снимки са готови за изтегляне |
| marks finalized | {client} финализира маркираните снимки | {client} избра снимките си за обработка |
| OTP | Ваш код за потвърждение | {code} е вашият код за вход |
| password reset | Смяна на паролата | Заявка за нова парола |

## Also true, deliberately NOT changed

- `verification_email.txt` / `verification_email_subject.txt` are **dead** — nothing references them. Flagged, not deleted.
- `base_email.html` names `'Playfair Display'` / `'Montserrat'` with no `@font-face`; webfonts never load in email, so every recipient already sees Georgia/Arial. `font_pair` can only pick the serif-vs-sans fallback.
- The `bg en` suffix in the reported screenshot was admin data typed into the WYSIWYG at send time; the DB value is clean now. Not a code bug.
- `accounts/views.py:24-51` duplicates `_brand_name()` from `main_app/emails.py`. Pre-existing.

## Deploy note

`SITE_URL` must be set in the production `.env` before deploy, or every emailed link
points at localhost.

## Verification plan

1. Migration for the 3 new `SiteConfiguration` fields + `brand_name_plain` help_text → `python manage.py migrate`
2. Tests: subject/body/link all `bg` regardless of active language; link has `/bg/` prefix; `&` renders once not as `&amp;` → `python manage.py test`
3. `makemessages -l bg -l en` + translate new msgids + `compilemessages`
4. Real send to a Gmail address; check light mode, dark mode, mobile.

## Resolved after advisor review (pre-implementation)

- `i18n_patterns(..., prefix_default_language=True)` → BG URLs DO carry `/bg/`. Test asserts
  equality with `reverse()` under `override(LANGUAGE_CODE)`, not a hardcoded prefix.
- Production `MEDIA_URL` is a public GCS bucket (absolute); DEBUG is `/media/` (relative).
  `email_logo` src = `urljoin(SITE_URL, logo.url)` so both work in an inbox.
- `('primary_color','background_color')` is already in `SiteConfigurationAdmin.CONTRAST_PAIRS`.
- **D17**: `site_config` must be injected at THREE sites: `_send_reservation_email`,
  `send_otp_email`, and `BrandedPasswordResetView.extra_email_context`.
- **D18**: subclass `PasswordResetForm.send_mail` to add `reply_to`, wired via `form_class`,
  so password reset is not the one email missing Reply-To.
- **D19**: use `override(settings.LANGUAGE_CODE)`, not a literal `'bg'`.

## Baseline (untouched code, 2026-09-19)

`Ran 516 tests — FAILED (failures=4, errors=8)`. Pre-existing. Any count above this is a regression.

## Implemented (2026-09-19)

New: `massageProject/main_app/email_context.py` (`site_language`, `email_url`, `email_branding`,
`build_email`), `templates/emails/_button.html`, `massageProject/main_app/tests_email_rendering.py`,
migration `0065_siteconfiguration_email_logo_and_more`.

Changed: `settings.py` (SITE_URL), `main_app/models.py` (html.unescape + 3 email fields),
`main_app/admin.py` (Имейли fieldset), `main_app/emails.py`, `accounts/emails.py`,
`accounts/views.py` (BrandedPasswordResetForm + site_language), `main_app/views.py`
(3 call sites + `_send_client_email` hook signature), all 5 HTML emails + their
`.txt` bodies and subjects, both locale catalogs.

Defect found and fixed during implementation: `django.utils.translation.override`
calls `deactivate_all()` on exit when no language was active, leaving translations
switched off for everything that followed. Replaced by `site_language()`, which
restores `settings.LANGUAGE_CODE`. Covered by
`test_sending_does_not_switch_translations_off_afterwards`.

Result: 525 tests, 4 failures / 8 errors — identical to the recorded baseline.

TODO by the owner: set `SITE_URL` in the production `.env` (it is not there yet;
the dev default is http://localhost:8000).

## Code review findings (2026-09-19, /code-review high)

Two real defects in this diff, both fixed with a regression test each:

1. **High** — `build_email` called `email_branding()` *before* entering `site_language()`.
   `brand_name` is a modeltranslation field, so the From header, HTML header and both
   footers followed the visitor's language while the subject and bodies followed the
   site's. The exact bug the module claims to fix, in the one field that reads the DB.
   Test: `test_brand_name_is_taken_from_the_site_language`.
2. **Medium** — autoescaping applies to `.txt` templates too, so the new footer blocks
   leaked `&amp;` / `&quot;` into every `text/plain` part. The project's own default
   brand name (`Relax & Health`) contains an ampersand, so it fired out of the box.
   Fixed with `{% autoescape off %}` around the footer in all five text bodies.
   Test: `test_plain_text_part_is_not_html_escaped`.
3. **Medium** — `SITE_URL` was absent from `.env.example`. Added with a comment.

Two further findings are in the **pre-existing, uncommitted proofing-bucket-cleanup
work, not this diff** — left alone deliberately:
- `models.py` `unlock_proofing()` clears `proofing_finalized_at` but leaves
  `proofs_purged_at` stamped, so a second round of unmarked frames is never purged.
- `signals.py` `_delete_image_derivatives` lets storage errors propagate from inside
  `QuerySet.delete()`'s transaction, so one transient GCS error rolls back the DB
  delete after blobs are already gone.

Final: 528 tests, 4 failures / 8 errors — identical to baseline.

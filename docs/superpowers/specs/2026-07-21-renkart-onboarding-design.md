# RenkArt Onboarding — Design

**Date:** 2026-07-21
**Depends on:** Part 2 (Brand Configuration) — `SiteConfiguration`, theming, terminology
templates, and feature flags, all merged to `main` prior to this design.
**Research:** `docs/superpowers/research/renkart-site-import.md` (site content, pricing,
contact info, visual identity, image-extraction findings — gathered 2026-07-20).

## Goal

Populate a second, isolated local database with real RenkArt (photography studio)
content, using the now-complete white-label mechanics (Part 2) — no template or model
changes beyond one small pre-existing bug fix (currency label) discovered during this
design pass. This is local onboarding/preview work, not a production deploy (Part 3,
per-brand deploy infra, is intentionally not built yet).

## Decisions carried over from the earlier brainstorming session (2026-07-20)

See `docs/superpowers/research/renkart-site-import.md`'s "Decisions already made" section:
booking kept as inquiry/request semantics, pull from all public pages, real media reuse
authorized, separate Postgres DB per brand, re-theme only (no layout changes), no
massage-vocabulary relabeling in code (handled by Part 2's terminology fields instead), a
few realistic demo reservations/comments are fine.

## New decisions made in this design pass

1. **DB switching mechanism**: since Part 3 (per-brand `.env`/infra) doesn't exist yet,
   switch locally by editing `.env`'s single `DATABASE_URL` value between the massage
   site's DB and RenkArt's DB. No new settings code — matches how the single-env-file
   setup already works today.
2. **Image sourcing**: proceed with only the 2 images already confirmed
   scriptable-downloadable in the earlier research (`logo33.jpg`, `reneta.jpg`). The
   remaining ~15-18 portfolio photos resisted automated extraction (likely an
   anti-hotlink gallery script) and are explicitly out of scope for this pass — the
   client can upload real portfolio photos later via the admin, once Part 2's
   theming/gallery mechanics are live for her brand.
3. **Currency**: the site's main currency becomes EUR. This surfaced a pre-existing,
   sitewide gap unrelated to RenkArt specifically — price display is hardcoded to the
   Bulgarian leva label (`{% trans "лв" %}` / `{% trans "лв." %}`) in 5 templates, not a
   configurable field. Fixed as a small, surgical, site-wide template text change (see
   below) since the user wants EUR as the site's primary currency now, for both the
   existing massage business and RenkArt.

## Part A — Currency label fix (site-wide)

Replace the hardcoded currency label in all 6 occurrences across 5 templates with `€`:

- `templates/partials/featured_with_image.html:14` — `{% trans "лв." %}` → `{% trans "€" %}`
- `templates/partials/featured_without_image.html:11` — `{% trans "лв." %}` → `{% trans "€" %}`
- `templates/pages/my_profile.html:64` — `{% trans "лв" %}` → `{% trans "€" %}`
- `templates/pages/my_profile.html:133` — `{% trans "лв" %}` → `{% trans "€" %}`
- `templates/pages/services_page.html:296` — `{% trans "лв" %}` → `{% trans "€" %}`
- `templates/pages/reservation.html:36` — `{% trans "лв" %}` → `{% trans "€" %}`

No model/field changes — `Service.price` is already a plain `DecimalField` with no
currency concept attached, so this is purely a display-label swap. The old `лв`/`лв.`
msgids become obsolete (not deleted) in the catalog regen; new msgid `€` gets `msgstr
"€"` in both bg and en (a currency symbol needs no translation, but the codebase's
existing convention wraps these labels in `{% trans %}`, so the fix keeps that
consistent rather than removing the tag).

No existing test asserts on `"лв"` text (confirmed via grep), so no test changes are
needed for this part — it's a pure text swap.

## Part B — Local DB setup (manual, not code)

1. `createdb renkart_db` locally (or `psql` equivalent) using the same Postgres role
   already used for `massage_db`.
2. To work on RenkArt: edit `.env`'s `DATABASE_URL` to
   `postgres://signal:ialangis@localhost:5432/renkart_db`, then `python manage.py migrate`.
3. To go back to the massage site: edit `.env`'s `DATABASE_URL` back to
   `postgres://signal:ialangis@localhost:5432/massage_db`.

This is a manual local workflow, not new application code. Documented in the plan's
task steps so whoever runs it later has the exact commands.

## Part C — `populate_renkart` management command

New file: `massageProject/main_app/management/commands/populate_renkart.py`. Follows
`populate_db.py`'s existing conventions: one `Command.handle()`, numbered inline steps,
`get_or_create` throughout (idempotent — safe to re-run), `self.stdout.write` progress
lines. Real images (`logo33.jpg`, `reneta.jpg`) are downloaded from
`https://renkart.net/images/...` into `media/` under the command (mirrors how
`populate_db.py` references image paths, but these are fetched rather than
already-committed fixtures).

### Content plan, model by model

All translated fields (per `massageProject/main_app/translation.py`) get both bg and en
values set explicitly — bg text adapted/paraphrased from the real site (it's the only
source language), en text is new translation work (no English original exists).

- **`SiteConfiguration`** (singleton, `get_solo()`):
  - Colors: near-black/white/warm-grey base (`primary_color`≈`#1A1A1A`,
    `background_color`≈`#FAF8F5`, `text_color`≈`#1A1A1A`) + one muted accent
    (`accent_color`≈ warm gold `#B08D57`) for links/buttons/CTAs, per the research doc's
    recommended re-theme direction.
  - `font_pair='playfair_montserrat'` (already fits; no change needed per research).
  - `style_preset='soft'` (default; photography portfolio reads fine with the existing
    soft radius/shadow treatment).
  - `hero_variant='fullbleed'` — best showcase for one strong full-width portrait image
    (the only real hero photo available), vs. `split` (needs two content areas) or
    `carousel` (needs multiple images to rotate).
  - Terminology: `service_singular/plural` = фотосесия/фотосесии (photo
    session/sessions), `specialist_singular/plural` = фотограф/фотографи
    (photographer/photographers) — bg and en both set.
  - Feature flags: all three (`booking_enabled`, `comments_enabled`,
    `google_login_enabled`) stay `True` — the existing inquiry-style booking flow, UGC
    reviews, and Google login all apply cleanly to a "request a session" model.

- **`BusinessInfo`**: name "RenkArt", address/phone/email from the research doc, bg+en
  description (paraphrased bio: fine arts background, photography since 2008–2012 in
  Italy, portrait/art focus, diptych work), `facebook_link` set, `instagram_link`/
  `tik_tok_link` left blank (none found), `main_image` = `reneta.jpg`.

- **`Specialist`** (Reneta Kirilova): `image` = `reneta.jpg`, bg+en bio (same
  paraphrase, specialist-scoped version), contact fields from the research doc.

- **`WorkingHours`** (per-specialist, drives actual slot-booking mechanics): placeholder
  Tue–Sat 10:00–18:00, closed Sun/Mon (a photography studio is plausibly closed Mondays
  rather than weekends, unlike the existing massage business's Mon–Sat pattern). Flagged
  in the command's final summary output as **needing real confirmation from the client
  before go-live** — no real hours were published on the source site.

- **`BusinessWorkingHours`** (free-text display rows on the about/contact page): a
  matching bg+en label ("Вторник – Събота" / "Tuesday – Saturday", "10:00 - 18:00"),
  same placeholder caveat.

- **`ServiceGroup`** ×3 + **`Service`** entries, EUR prices taken directly from the
  research doc (no BGN conversion needed now that currency is EUR):
  1. **Портретни фотосесии / Portrait Sessions** — Мини (studio, 15 photos, €120),
     Мини (outdoor, 15 photos, €130), Голям пакет (35 photos, €220), Макси пакет (50
     photos, €280). `duration_in_minutes` placeholders: 60/60/90/120 (portrait sessions
     scale with package size; flagged as estimates, not published on the source site).
  2. **Fine Art фотосесии / Fine Art Portraits** — individual (€140), couples (€160),
     families (€180), children (€120), Макси пакет 30 photos (€280).
     `duration_in_minutes` placeholder: 90 for all (studio-based, similar setup time).
  3. **Арт / Будоар фотосесии / Art & Concept Sessions** — one `Service` entry, price
     set to a clearly-labeled starting placeholder (€150) with "цена по договаряне"
     ("price by arrangement") stated in both the short and long bg+en descriptions,
     since the real site publishes no fixed price for this category.
     `duration_in_minutes` placeholder: 180 (matches the research doc's "2–8 hours
     depending on concept" — using the low end as a floor estimate).
  - `home_page=True` on 3 services total (the model's existing max-3 cap): one from
    each group, to populate the homepage's featured-services section.
  - `Service.image` (required field, no real per-service photos available): reuse
    `reneta.jpg` across all service entries as a shared placeholder — it's real,
    on-brand, and not visually embarrassing, unlike reusing an unrelated massage stock
    photo. Flagged in the command's summary as needing real per-service photos later.

- **`Gallery` + `Image` + `HomePage`**: one `Image` wrapping `reneta.jpg` added to the
  homepage's `Gallery` (feeds the `fullbleed` hero and any gallery grid). `HomePage.logo`
  = `logo33.jpg`. `HomePage.brand_name`/`description`/`footer_tagline` bg+en, adapted
  from the research doc's bio.

- **`Comment`** ×4–5: realistic demo reviews in Bulgarian only (`Comment.content` has no
  modeltranslation fields — matches the model's actual shape), photography-appropriate
  wording (not massage-flavored), `is_reviewed=True` so they render immediately.

- **`Reservation`** ×3–4: demo bookings against the real `Service`/`Specialist` records,
  mixing 1–2 past/completed and 2 upcoming, reusing `populate_db.py`'s
  `next_working_day()` helper pattern so seeded times always land within Reneta's
  placeholder working hours.

### Command safety / idempotency

Every creation step uses `get_or_create` keyed on a natural identifier (name, email,
etc.), matching `populate_db.py` exactly — re-running the command must not create
duplicate rows. `SiteConfiguration`/`HomePage` are true singletons via their own
`get_solo()`/`save()` guards, so re-running only ever updates the same row.

## Testing

One new test file, `massageProject/main_app/tests_populate_renkart.py`:
- Running the command once creates the expected non-zero counts for each model
  touched (`Service`, `Specialist`, `BusinessInfo`, `Comment`, `Reservation`, etc.).
- Running the command a second time does not change any of those counts (idempotency).
- `SiteConfiguration.get_solo()` reflects the RenkArt terminology/colors after running.

This mirrors the existing test suite's style (behavioral assertions on counts/state, not
line-by-line content matching) and doesn't attempt to test against the live
`massage_db` — it uses Django's isolated test database, so no manual DB switch (Part B)
is needed to run it.

## Out of scope (unchanged from the 2026-07-20 research/brainstorm)

- News/seasonal campaign content — no model exists for it; a real future feature, not
  built now.
- Part 3 (deployment platform, per-brand VPS/env infra).
- The remaining ~15-18 curated portfolio photos beyond the 2 already confirmed
  downloadable.
- Any relabeling of massage-domain vocabulary in code (`verbose_name`s, model names) —
  Part 2's terminology fields already handle brand-facing wording.

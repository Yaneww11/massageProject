# Dark theme — implementation log (Direction A, Gallery Black)

## Step 01 — surface tokens promoted  ✅ code complete
- `models.py` — three new `SiteConfiguration` fields: `surface_sunken_color`,
  `surface_paper_color`, `surface_raised_color`, each with frontend-locating `help_text`.
- `theme.py` — all 9 existing presets gained the three surface values, so light presets keep working.
- `theme_overrides.html` — renders `--bg-sunken`, `--bg-paper`, `--bg-raised`.
- `variables.css` — matching fallbacks.
- `admin.py` — new fields added to `COLOR_FIELDS` and the colour fieldset;
  `CONTRAST_PAIRS` extended with `text_color` vs `surface_paper_color` and vs `surface_sunken_color`.
- `tests_theme.py` — preset field guard extended; new
  `test_every_preset_text_passes_contrast_against_every_surface` (text + muted vs all four surfaces, ≥4.5).
- Migration `0053`.
- Verified: `--bg-paper` is read 33× in CSS, so the token is live, not dead plumbing.

## Step 02 — Gallery Black preset, made default  ✅ code complete
- `theme.py` — new `gallery_black` preset, listed first.
- Model defaults for all 11 colour fields flipped to the dark palette;
  `color_preset` default is now `gallery_black`.
- `variables.css` — `:root` fallbacks re-pointed to the dark palette.
- Migration `0054` (field defaults) + `0055` (data migration applying the preset to the
  existing singleton row, reversible to `warm_earth`).
- Locale: new label "Галерийно черно" / "Gallery Black" translated in bg + en, compiled.

### Deviation from the approved proposal
`--secondary-color` turned out to be used as a **text** colour in `footer.css` and
`my_profile.css` (in the light theme it is the pale taupe on the dark brown footer), not only
as a button fill. The proposed `#2B2B2F` would have been invisible there, so secondary is
`#A8A8A4` — 8.80:1 as a fill with auto-black text, 7.05:1 worst case as text on `--bg-raised`.
`#2B2B2F` remains the border colour.

### Final palette as shipped
| Token | Hex |
|---|---|
| `--bg-sunken` | `#060607` |
| `--bg-light` | `#0A0A0B` |
| `--bg-paper` | `#141416` |
| `--bg-raised` | `#1D1D20` |
| `--text-main` | `#F2F2F0` |
| `--text-muted` | `#A3A3A0` |
| `--primary-color` | `#EDEAE4` |
| `--primary-light` | `#FFFFFF` |
| `--secondary-color` | `#A8A8A4` |
| `--accent-color` | `#C89B6A` |
| `--border-color` | `#2B2B2F` |

`on_color()` resolves black for every fill, as designed — no helper change needed.

## Known items deferred to later steps
- `--white` (21 CSS uses) and literal `#fff` — step 04 sweep.
- `--success-light` / `--error-light` and the literals in `form.css:96-104` — step 03.
- `--shadow-*` are still `rgba(0,0,0,…)` from the style preset — step 03.
- `my_profile.css:751` uses `color: var(--border-color)` — invisible on dark, fix in step 05.
- `reservation.css:636` uses `--border-color` as a background — check in step 05.
- `--gallery-dark-bg: #121212` to be retired in favour of `--bg-sunken` — step 05.

## Verification after step 02
Baseline captured from a clean `HEAD` worktree (`git worktree add`), because the suite is not
green on `main`. Runs must be **sequential** — the project uses Postgres, so two concurrent
`manage.py test` runs collide on `test_renkart_db` and hang at an interactive prompt.

- Baseline (clean HEAD): 397 tests, **17 errors + 3 failures**.
- After steps 01+02: 398 tests, same 17 errors + 3 failures, plus two tests that
  legitimately encoded the old light defaults and were updated:
  - `SiteConfigurationDefaultsTest.test_defaults_match_current_spa_theme`
    → renamed `test_defaults_match_gallery_black_theme`, now asserts the dark palette
      including the three surface tokens and `color_preset == 'gallery_black'`.
  - `ThemeOverridesRenderingTest.test_home_page_includes_theme_colors_and_font_link`
    → asserts the dark `--primary-color` and the three new surface vars, and the
      `--on-*` values that `on_color()` now resolves to black.

Net regression from this work: **zero**.

### Pre-existing breakage on `main` (not caused by this work)
17 errors + 3 failures, concentrated in `tests_about_page`, `tests_comments`,
`tests_terminology`, `tests_theme` (hero variants) and `tests_site_configuration`
(context processor). Worth triaging separately — several sit in the same files the
theme work touches, so they are not providing coverage where it is most needed.

## Step 03 — elevation and status colours  ✅ code complete

### Approach
Semantic colours and shadow tints are **derived from the background colour**, not stored as
admin fields — the site owner never picks "the error red", so adding three more colour pickers
would be noise. `theme.py` gained `is_dark()` and `derived_theme_vars(bg_hex)`, exposed to
templates through a `derived_vars` filter and rendered in `theme_overrides.html`. Every preset,
light or dark, therefore gets semantic colours that suit its own ground.

### Shadows
`STYLE_PRESETS` keeps owning shadow geometry (offset/blur, so the admin's style choice still
works), but the colour moved to `--shadow-tint-sm/md/lg`, which deepens on a dark ground:
`rgba(0,0,0,0.05/0.1/0.15)` on light becomes `rgba(0,0,0,0.4/0.55/0.7)` on dark. The `sharp`
preset's `shadow_sm: none` is untouched.

### New tokens
`--success-light` / `--error-light` (now dark washes on a dark theme), plus `--on-success` /
`--on-error`, mirroring the existing `--on-primary` pattern. These were needed because
`--success` is used **both** as text on the canvas (`form.css`, `my_profile.css`) and as a
background with text on it (`photo_proofing.css:383`, the finalized ribbon, which used
`var(--white)` and would have been unreadable on a light sage fill).

### Literals removed
- `form.css:96-104` — `#FEE2E2 / #FECACA / #ECFDF5 / #D1FAE5` → `--error-light` / `--success-light`.
- `reservation.css:522` — `#ECF1E7` → `--success-light`.
- `photo_proofing.css:383` — `var(--white)` → `var(--on-success)`.

### Pre-existing accessibility bug found and fixed
The light theme's `--success: #6B7A5E` reached only **4.30:1** on the cream background
(**3.80:1** worst case across all light presets' surfaces), and `--error: #A35D5D` only
**4.05:1**, failing even against its own `#FEF2F2` wash at 4.48:1. Both were below WCAG AA
*before* this redesign. Darkened within the same hue family to `#576648` (5.11 worst case)
and `#8C4746` (5.59), preserving the muted sage / terracotta character.

### Dark values shipped
| Token | Hex | Worst contrast |
|---|---|---|
| `--success` | `#9CBE87` | 8.11 on `--bg-raised`, 8.10 on its wash |
| `--success-light` | `#17200F` | — |
| `--error` | `#E59A95` | 7.52 on `--bg-raised`, 7.95 on its wash |
| `--error-light` | `#251312` | — |

### New tests (`DerivedThemeVarsTest`)
Five tests, run across **all ten presets**: washes match their theme's brightness; success and
error clear 4.5:1 on all four surfaces; they clear 4.5:1 on their own wash and against their
`on_*` colour; dark grounds get deeper shadow tints than light ones; every style preset's
shadows reference the tint variable rather than a literal.

No new translatable strings in this step.

## Step 04 — hardcoded colour sweep  ✅ code complete

34 edits across 9 stylesheets. **Zero hardcoded hex colours and zero brand-tinted `rgba()`
remain** anywhere in `staticfiles/css` outside `variables.css` (and the Django-admin stylesheet,
which themes the admin, not the site).

### The `--white` question — classified, not blanket-replaced
The 21 uses of `var(--white)` split into two genuinely different roles:

- **Theme surface or text on a themed fill (9 uses)** — retokenised:
  `form.css:60` focus background → `--bg-paper`; `reservation.css:313` the "today" dot on a
  selected (accent-filled) day → `--on-accent`; `home.css:363-378` the `.hp-gallery--dark`
  block → `--text-main` / `--text-muted` / `--primary-color` / `--on-primary`;
  `photo_proofing.css:337` the compare badge, which paired `--white` with
  `color: var(--primary-color)` and would have rendered bone-on-white at 1.06:1 in the dark
  theme → now `--primary-color` fill with `--on-primary` text.
- **Chrome sitting on a photograph or scrim (12 uses)** — left as `--white`, in
  `gallery.css`, `hero-fullbleed.css`, `hero-carousel.css` and `photo_proofing.css`. The ground
  there is the image, not the theme, so white is correct in any theme. `variables.css` now
  documents that role on the token.

### Other changes
- `--gallery-dark-bg: #121212` **retired** — its three uses now read `--bg-sunken`, so the
  gallery bands sit on the theme's own ladder instead of a fixed near-black.
- `home.css:8` `--hp-sunken` was a literal `#F2EBE2`; now aliases `--bg-sunken`.
- Brown-tinted shadows (`rgba(74,55,40,…)` etc., 6 uses) → `--shadow-md` / `--shadow-lg`,
  so they follow the tint derived in step 03.
- Focus/selection rings that were brand-tinted rgba (`form.css`, `my_profile.css`,
  `reservation.css`) → `color-mix(in srgb, var(--accent-color) 25%, transparent)`.
  `color-mix` was already in use at `photo_proofing.css:283`, so this adds no new requirement.
- Warm-brown scrims over photographs (`gallery.css` gradient, lightbox, overlay buttons;
  `my_profile.css` review-modal overlay) neutralised to black at the same alpha — the warm cast
  belonged to the old palette and tinted the photographs.
- `reservation.css:365-367` disabled time slot: `#eee/#ccc/#999` →
  `--bg-sunken` / `--border-color` / `--text-muted`, as specified in the proposal.
- `header.css:168` dropped its `var(--border-color, #e8e0d8)` literal fallback.

### New regression guard (`StylesheetTokenUsageTest`)
Two tests walk all 19 non-exempt stylesheets and fail on any hardcoded hex colour or any
brand-tinted `rgba()`. This turns the CLAUDE.md "never hardcode hex values" rule into something
enforced rather than remembered. Neutral black/white scrims are deliberately allowed, since
they are ground-independent.

## Code-review fixes (post steps 01–04)

A two-axis review (standards + spec) against the approved proposal found two real defects.

### 1. `--primary-color` inverted to bone while still backing large chrome  (spec axis, blocking)
Step 02 flipped `--primary-color` to bone `#EDEAE4` on the strength of its 48 uses as a *text*
colour. Its 21 uses as a **background** were counted but never examined. Four of them are large
chrome surfaces, which became near-white slabs on a site that is meant to be predominantly
black — and footer links (`--secondary-color` on the footer bar) landed at **1.99:1**, a clear
AA failure that the automated guards could not catch, because both tokens are legitimate and
only their pairing is wrong.

Re-grounded the four chrome surfaces onto the surface ladder:

| Location | Was | Now |
|---|---|---|
| `footer.css:3` whole footer bar | `--primary-color` | `--bg-sunken` |
| `about.css:100` stats band | `--primary-color` | `--bg-sunken` |
| `responsive.css:6` mobile nav panel | `--primary-color` | `--bg-paper` |
| `header.css:212,224` hamburger bars | `--primary-color` | `--text-main` |

Plus the text sitting on them: 8 `var(--on-primary)` in `footer.css` and 2 in `about.css`
(including a `color-mix`) → `var(--text-main)`, since `--on-primary` is black and was only ever
correct against a bone slab.

Footer links: **1.99:1 → 8.49:1**. Footer body text 18.07:1. Mobile nav 16.41:1.

The other **16** primary backgrounds were deliberately left alone after inspecting each: they
are small fills — `.btn-primary`, `.btn-outline:hover`, `.lang-btn.active`, the profile avatar
circle, `.btn-calendar`, `.btn-primary-profile`, `.time-slot:hover`, `.toast`, the gallery
button hover, and five photo-proofing active states (filter buttons, 30px circles, label chips).
Bone-on-black is correct there and is the intended look.

*Open judgement call for step 05:* `my_profile.css:122` `.next-booking-date-block` is a padded
bone tile rather than a button. Kept as a deliberate inverted highlight; revisit on the profile pass.

### 2. `help_text` on the three surface fields was factually wrong  (standards axis, hard violation)
CLAUDE.md requires help_text naming the page/section a field affects, in plain language, for a
non-technical owner. The text claimed locations the tokens do not touch — `surface_sunken_color`
named photo proofing and the footer (the footer was `--primary-color` at the time, and photo
proofing has no `--bg-sunken` at all), and `surface_paper_color` named the sign-in modal, whose
panel is `--bg-raised`. The wrong strings were frozen into migrations 0053/0054 and translated
into both catalogues.

Rewritten from the actual token map (`grep var(--bg-*)`), corrected in `models.py`, patched in
place in the two untracked migrations, and retranslated in bg + en. `makemigrations --check`
reports no drift.

### Accepted but not actioned in this pass
- Migration 0055 still overwrites the existing singleton (kept deliberately — the user confirmed).
  The frozen-migration concern (importing `COLOR_PRESETS` from live app code) stands and is
  worth revisiting before deploy.
- Focus ring duplicated verbatim in 3 files → one `--focus-ring` token.
- `is_dark()` restates `on_color()`'s `0.179` threshold instead of reusing it.
- `StylesheetTokenUsageTest.CSS_ROOT` is cwd-relative; should use `settings.BASE_DIR`.
- The guard test covers `.css` but not templates, which CLAUDE.md also names.
- `gallery.css:90` `.gal-tile__bg` placeholder is still light — step 05.
- Pre-existing, unrelated: `responsive.css:19` references `var(--font-color)`, which is not
  defined anywhere.

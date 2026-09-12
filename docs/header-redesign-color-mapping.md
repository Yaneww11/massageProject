# Header Redesign — design colour → dynamic token mapping

Source design: `# Header redesign – photography site` handoff bundle, `Header Redesign.dc.html`.
Target artboards: **Turn 2** (`2a`–`2e`) — "Rebuilt to your answers — real logo · Old Standard TT
wordmark · 2-item nav with dropdown · hide-on-scroll · full-screen white overlay".

Turn 2 is the newest turn (sections render newest-first: `t2`, then `t1`, then the `t0` brief).
Turn 1 (`1a`–`1f`) is the superseded earlier exploration and is **not** being implemented.

## Rule being applied

No colour value from the design file is copied into the codebase. Every design colour is mapped to
the dynamic token that best matches it *semantically*, so the header follows whatever palette is
configured in `SiteConfiguration`.

This is enforced by `StylesheetTokenUsageTest` (`massageProject/main_app/tests_theme.py:221`):

- `test_no_hardcoded_hex_colors_outside_variables_css` — no `#rrggbb` outside `base/variables.css`
- `test_no_brand_tinted_rgba_outside_variables_css` — no `rgba()` except neutral
  `rgba(0,0,0,…)` / `rgba(255,255,255,…)`

Tint ladders from the design (`rgba(74,47,38,.07)`, `.12`, …) are reproduced as
`color-mix(in srgb, var(--token) N%, transparent)` — derived from the token, no literal.

## Surfaces

| Design element | Design colour | Token |
|---|---|---|
| Header bar background (2a, 2c) | `#fff` | `--bg-paper` |
| Compact header, translucent (2b) | `rgba(255,255,255,.94)` | `color-mix(in srgb, var(--bg-paper) 94%, transparent)` |
| Dropdown panel background | `#fff` | `--bg-paper` |
| Mobile full-screen overlay | `#fff` | `--bg-paper` |
| Profile button background | `#fff` | `--bg-paper` |
| BG/EN segmented track | `rgba(28,20,17,.055)` | `--bg-raised` |
| Nav / dropdown item hover | `rgba(28,20,17,.05)`, `.04`, `.06` | `--bg-raised` |
| Dropdown trigger tint (hover) | `rgba(74,47,38,.07)` | `color-mix(in srgb, var(--primary-color) 7%, transparent)` |
| Dropdown trigger tint (open/current) | `rgba(74,47,38,.12)` | `color-mix(in srgb, var(--primary-color) 12%, transparent)` |
| Dropdown item active | `rgba(74,47,38,.07)` | `color-mix(in srgb, var(--primary-color) 7%, transparent)` |

## Text

| Design element | Design colour | Token |
|---|---|---|
| Wordmark "RENKART" | `#1c1411` | `--text-main` |
| Logo tagline "Фотография · Пловдив" | `rgba(28,20,17,.52)` | `--text-muted` |
| Nav link default ("За мен") | `#3a2c26` | `--text-muted` |
| Nav link hover | `#1c1411` | `--text-main` |
| Dropdown item default | `#241a16` | `--text-main` |
| Dropdown hash hints (`#home`, `#services`) | `rgba(28,20,17,.35)` | `--text-muted` |
| Dropdown trigger, open/current | `#4a2f26` | `--primary-color` |
| Dropdown item, active | `#4a2f26` | `--primary-color` |
| Inactive language button | `rgba(28,20,17,.62)` | `--text-muted` |
| Active language button label | `#fff` | `--on-primary` |
| CTA label + icon | `#fff` | `--on-primary` |
| Hamburger / close icon stroke | `#1c1411` | `--text-main` |
| Profile icon stroke | `#4a2f26` | `--primary-color` |

## Fills, borders, effects

| Design element | Design colour | Token |
|---|---|---|
| CTA background | `#4a2f26` | `--primary-color` |
| CTA hover background | `#33201a` | `--primary-light` (the token's designated primary-hover role) |
| Active language button fill | `#4a2f26` | `--primary-color` |
| Top 4px brand strip (2a) | `#4a2f26` | `--accent-color` |
| Submenu left rule (mobile) | `rgba(74,47,38,.18)` | `color-mix(in srgb, var(--primary-color) 18%, transparent)` |
| Header bottom hairline | `rgba(28,20,17,.10)` | `--border-color` |
| Dropdown panel border | `rgba(28,20,17,.08)` | `--border-color` |
| Overlay header / footer rules | `rgba(28,20,17,.08)` | `--border-color` |
| Vertical divider pipe | `rgba(28,20,17,.12)` | `--border-color` |
| Profile button border | `rgba(28,20,17,.16)` | `--border-color` |
| Profile button hover border | `rgba(28,20,17,.42)` | `--primary-color` |
| CTA resting shadow | `0 1px 2px rgba(28,20,17,.25)` | `--shadow-sm` |
| CTA hover shadow | `0 4px 14px rgba(74,47,38,.30)` | `--shadow-md` |
| Compact header shadow | `0 8px 24px rgba(28,20,17,.09)` | `--shadow-md` |
| Dropdown panel shadow | `0 18px 44px rgba(28,20,17,.16)` | `--shadow-lg` |
| Focus ring (inner gap / outer) | `#fff` / `#4a2f26` | `--bg-paper` / `--accent-color` |

`--accent-color` is used for focus rings because `variables.css` documents that token's role as
"links, focus rings, one CTA".

## Not colours, same principle

| Design value | Not hardcoded — instead |
|---|---|
| Jost (nav, UI, buttons) | `--font-main` |
| Old Standard TT (wordmark) | `--font-heading` |
| Google Fonts `<link>` in the design's `<helmet>` | dropped — `theme_overrides.html` already emits `{{ pair.google_fonts_url }}` from `font_pair` |
| 6px / 7px / 8px control + panel radii | `--radius-md` |
| `assets/renkart-logo.png` | `{{ brand_logo }}` |
| Literal wordmark text "RENKART" | `{{ brand_name_plain }}` |

The design's own brief card confirms the logo is a placeholder: *"No logo file supplied → the crest
is a placeholder monogram, swap in the real SVG."*

Layout values that carry no theme meaning — header heights (88px → 64px), the 56px page gutter,
44/48px tap targets, animation timings — are taken from the design as-is.

## Consequence of mapping rather than copying

The design is white surfaces, brown brand, near-black text. The active preset is **Gallery Black**
(dark). Mapped to tokens, the header renders dark — it will not look like the artboards. The
artboards show what it looks like under a light preset. Structure, spacing, states and behaviour
match the design exactly; only the palette follows the configured theme.

## Decisions taken during implementation

- **Nav copy stays `За нас`.** The msgid is unchanged, so no catalog churn. The compiled Bulgarian
  catalog already maps `За нас` → `За мен`, so Bulgarian renders "За мен" and happens to match the
  design's copy. This predates the redesign — the previous header used the same `{% trans %}` tag.
- **No tagline.** The design's "Фотография · Пловдив" is dropped; there is no header tagline field
  on `SiteConfiguration` and adding one was out of scope.
- **The wordmark is the no-logo fallback.** The design pairs a small square crest with a "RENKART"
  wordmark, but a configured `brand_logo` usually already contains the brand name — rendering both
  duplicated it. So the logo shows when one is configured, and the wordmark only when one is not;
  the brand is never absent either way.
- **Wordmark is not uppercased.** The design's "RENKART" is an uppercase string literal, not a CSS
  transform, so `{{ brand_name }}` renders as configured, clamped (`24ch` desktop / `14ch` mobile,
  ellipsis) purely as a guard against a very long name reaching the centred nav.
- **Logo sizing is height-driven.** The design's crest is a 56×56 square; a real logo is usually
  wider than tall, and a fixed square letterboxed it. Height sets the size (56px → 38px compact,
  40px mobile) with `width: auto` and a `max-width` cap.
- **`resposive_menu_button.js` removed**, superseded by `staticfiles/js/header.js` (scroll state,
  dropdown, profile menu, overlay, submenu, current-section marking).
- **Dead `.navbar .menu` / `.navbar-toggle` rules removed** from `base/responsive.css` — they hung
  off the `.navbar` class this redesign deletes and referenced a non-existent `--font-color`.
- **`tests_feature_flags` assertion updated** from `navbar-cta` to `site-cta`; left as-is it would
  have passed vacuously against a class that no longer exists.

## One token no longer reaches the header

`--secondary-color` is now unused here. It previously drew the `.lang-btn` and `.user-menu-toggle`
borders; both moved to `--border-color`, which is the hairline token those borders actually are
(obs 7088 flagged `--secondary-color` as semantically overloaded). Consequence: changing that
swatch in the admin no longer affects the header.

## Test results

| Run | Result |
|---|---|
| `tests_theme` before any change | 33 tests, 1 failure (`HeroVariantSelectionTest`, pre-existing per obs 7056) |
| `tests_theme` + `tests_feature_flags` after | 52 tests, 1 failure — same pre-existing one |
| `tests_about_page` at HEAD (baseline) | 22 tests, 2 failures + 4 errors |
| `tests_about_page` after | identical 2 failures + 4 errors — none introduced |

Both token guards (`test_no_hardcoded_hex_colors_outside_variables_css`,
`test_no_brand_tinted_rgba_outside_variables_css`) pass.

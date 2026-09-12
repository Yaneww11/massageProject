# Dark theme — design proposal (Phase 2, no code)

Decisions from discovery:
- Dark becomes the **site's default look** (not just one more selectable preset).
- Applies to **both flavours** (booking site and photographer site).
- **Keep the current font pair** (`site_config.font_pair`, default Playfair Display + Montserrat).
- Reference vibe: **editorial photography** — near-black canvas, images carry the page, minimal chrome.

---

## 1. What the codebase already gives us (and what it doesn't)

Good news — the CSS is already token-driven:

| Fact | Consequence |
|---|---|
| `theme_overrides.html` is included *after* `styles.css` in `base.html:11-12` | DB colours already win at equal `:root` specificity. No load-order bug. |
| 8 colours are `SiteConfiguration` fields | Those flip to dark with one preset dict + one migration. |
| Only ~22 hardcoded hexes outside `variables.css` (+ ~60 `rgba()/white` literals) | The sweep is small and enumerable, not a rewrite. |

Four gaps that will make a dark theme look broken if we don't close them:

1. **`--bg-paper: #FFFFFF`** is not a `SiteConfiguration` field. Cards, panels and modals would stay white on a black page. This is the single most important token to promote.
2. **`--success-light: #ECFDF5` / `--error-light: #FEF2F2` / `--white`** are light tints that glare on dark. Plus literal `#FEE2E2 / #ECFDF5 / #D1FAE5` in `components/form.css:96-104`.
3. **`--shadow-sm/md/lg` come from `STYLE_PRESETS` as `rgba(0,0,0,…)`** — a black drop shadow is invisible on near-black. Elevation must come from surface-level steps + hairline borders, not shadows.
4. **`--primary-color` is used as a *text* colour 48 times and as a *background* 18 times.** This is the key inversion: in dark mode `primary_color` must be a **light** value. Then `on_color()` automatically resolves to black for button fills, which is exactly the editorial "bone button on black" look. No code change needed to `on_color()` — it just works once the hex is light.

Constraint already enforced by `tests_theme.py:89-94`: every preset's `primary/primary_light/secondary/accent` must hit ≥4.5 against its auto-picked `on_color`. Both directions below are verified against it.

---

## 2. Shared foundations (identical in both directions)

**Surface ladder** — replaces shadows as the elevation language.

| Token | Role |
|---|---|
| `--bg-sunken` | Behind the canvas: full-bleed image bands, gallery strips, footer |
| `--bg-light` | The page canvas (existing `background_color` field) |
| `--bg-paper` | Cards, panels, modals, table rows (**newly themable**) |
| `--bg-raised` | Hover state of a card, dropdowns, popovers |

Each step is a small luminance lift (~1.08 contrast), so the hierarchy reads as *material*, not as *stripes*.

**Typography** — current font pair kept, sizes re-tuned for dark. Light text on dark optically thickens, so weights come **down**, tracking goes **up**:

- Headings: heading family, weight 400 (was 600/700), `letter-spacing: 0.01em`. On black, a 700 serif blooms.
- Display (hero): `clamp(2.5rem, 6vw, 4.5rem)`, weight 400, `line-height: 1.05`.
- Body: body family, weight 300–400, `line-height: 1.7` (up from typical 1.5 — dark needs more air).
- Muted text never below `--fs-sm` and never below 4.5:1.

**Spacing & shape** — spacing scale unchanged (`--space-xs`…`--space-xl`). Radius stays driven by `site_config.style_preset` so the admin's choice still works; dark just makes `sharp` the recommended default.

**Elevation, replacing shadows**
- Rest: `--bg-paper` + `1px solid var(--border-color)`.
- Hover: lift to `--bg-raised`, border brightens toward `--accent-color`, `translateY(-2px)` kept.
- Overlay (modal/dropdown): `--bg-raised` + a *wider, darker* shadow that reads as a scrim, plus a top hairline highlight — the only shadow that still works on dark.

**Focus states (WCAG 2.4.11 / 1.4.11)**
- `:focus-visible` → `outline: 2px solid var(--accent-color); outline-offset: 2px`.
- Accent hits 7.8:1 on the canvas in both directions, well past the 3:1 non-text requirement.
- Never `outline: none` without a replacement. Keyboard focus must be visible on image tiles too (photo proofing is a keyboard-heavy grid).

**Images on dark** — the editorial part
- Gallery tiles sit directly on `--bg-sunken` with no card chrome.
- A 1px `--border-color` inset on each image so white-heavy photos don't bleed into the page.
- Hover: image at 100% opacity, siblings dimmed to 0.65 — the page recedes, the photo advances.
- The existing fixed `--gallery-dark-bg: #121212` gets folded into `--bg-sunken` and retired.

---

## 3. Direction A — "Gallery Black"

Neutral, cold, gallery-wall. The photo is the only colour on the page. Closest to the editorial reference.

| Token | Hex | Contrast |
|---|---|---|
| `--bg-sunken` | `#060607` | — |
| `--bg-light` (canvas) | `#0A0A0B` | — |
| `--bg-paper` | `#141416` | 1.08 vs canvas |
| `--bg-raised` | `#1D1D20` | — |
| `--text-main` | `#F2F2F0` | **17.65** on canvas / 16.41 on paper |
| `--text-muted` | `#A3A3A0` | **7.83** / 7.28 |
| `--primary-color` | `#EDEAE4` (bone) | **16.48** as text; 17.49 as fill w/ auto-black |
| `--primary-light` | `#FFFFFF` (hover) | 21.00 as fill |
| `--secondary-color` | `#2B2B2F` | 14.10 as fill w/ auto-white |
| `--accent-color` | `#C89B6A` (bronze) | **7.87** on canvas; 8.35 as fill |
| `--border-color` | `#2B2B2F` | hairline, non-text |

Character: headings in bone serif, buttons are bone rectangles with black text, bronze used sparingly — links, focus rings, the active nav item, one CTA per page. Nothing else is coloured.

Where it shines: gallery, album, photo proofing, hero.
Watch-out: the booking flow (reservation calendar, profile tables) can feel clinical without the warm accent doing more work.

---

## 4. Direction B — "Warm Charcoal"

Same editorial restraint, but the black is warmed — it carries the current earthy brand forward instead of discarding it. Luxury-studio rather than gallery-wall.

| Token | Hex | Contrast |
|---|---|---|
| `--bg-sunken` | `#0A0907` | — |
| `--bg-light` (canvas) | `#100E0C` | — |
| `--bg-paper` | `#1B1714` | 1.08 vs canvas |
| `--bg-raised` | `#251F1A` | — |
| `--text-main` | `#F5EFE7` | **16.86** on canvas / 15.59 on paper |
| `--text-muted` | `#A99C8D` | **7.18** / 6.64 |
| `--primary-color` | `#E6D8C6` (warm bone) | **13.76** as text; 15.00 as fill w/ auto-black |
| `--primary-light` | `#F9F2E8` | 18.89 as fill |
| `--secondary-color` | `#2C2521` | 15.07 as fill w/ auto-white |
| `--accent-color` | `#C79A6B` (bronze) | **7.58** on canvas; 8.26 as fill |
| `--border-color` | `#352D26` | hairline, non-text |

Character: the whole page has a faint warm cast, so skin tones in photos sit naturally instead of looking cold-corrected. Continuous with the existing `#4A3728 / #8E735B` brand.

Where it shines: reservation/profile/about — the human, service-business pages. Also the safer choice for the booking flavour.
Watch-out: a warm cast very slightly tints how photos read; a purist photographer may object.

Both avoid pure `#000` on large areas, per the constraint. Both clear WCAG AA everywhere, and body text clears AAA (≥7:1).

---

## 5. Key screens under the new system

**Home / hero** — hero variant stays admin-driven (`site_config.hero_variant`). Full-bleed image on `--bg-sunken`, no overlay tint box; instead a bottom-up gradient from the canvas colour so the headline sits in real darkness. Headline in display serif weight 400, one bone `.btn-primary`, one `.btn-outline`.

**Gallery / album** — edge-to-edge grid on `--bg-sunken`, no cards, no gaps larger than `--space-sm`. Album title is the only chrome.

**Photo proofing** — the densest screen. Tiles on `--bg-sunken`; marked state = 2px `--accent-color` border + a bronze corner glyph (never colour alone — a shape too, for colourblind users). PhotoLabel chips on `--bg-raised` with accent text. Comment field on `--bg-paper`.

**Reservation** — calendar and time slots become the main colour test. Available slot: `--bg-paper` + border. Selected: `--primary-color` fill with auto-black text. Disabled: `--bg-sunken` + `--text-muted` (replacing today's literal `#eee/#ccc/#999` at `reservation.css:365-367`).

**Profile / specialist tables** — no zebra striping (it's noise on dark). Rows separated by a single `--border-color` hairline, hover lifts the row to `--bg-raised`.

**Header / footer / auth modal** — header on the canvas colour with a bottom hairline, becoming `--bg-paper` with a scrim shadow once scrolled. Modal on `--bg-raised` over an 80% black backdrop with a blur.

**Status colours** — `--success / --error` re-tuned for dark, and their `-light` tints become *dark* tints (low-saturation dark washes at ~10% alpha) rather than the current `#ECFDF5 / #FEF2F2`.

---

## 6. What Phase 3 will cost (so you approve it knowingly)

Per `CLAUDE.md`, each new themable colour needs a `SiteConfiguration` field + a var in `theme_overrides.html` + frontend-locating `help_text` + a migration.

1. **Tokens** — add `bg_sunken_color`, `bg_paper_color`, `bg_raised_color` to `SiteConfiguration`; wire into `theme_overrides.html`; migration; `help_text` per the admin-help rule. Existing light presets get sensible values so **they keep working**.
2. **Preset** — add the chosen dark palette to `COLOR_PRESETS` in `theme.py`, make it the default, re-point `variables.css` fallbacks. New Bulgarian label = new translatable string.
3. **Elevation & status** — shadow strategy, `--success/-light`, `--error/-light`; kill the literals in `components/form.css:96-104`.
4. **Hardcoded sweep** — 22 hexes + ~60 `rgba()/white` literals across `auth-modal.css`, `home.css`, `reservation.css`, `header.css`.
5. **Per-page pass** — gallery → photo proofing → reservation → profile → home/hero → header/footer/modal → auth/misc.
6. **Verify** — `python manage.py test`, incl. `tests_theme.py` contrast assertions; then `makemessages -l bg -l en` + `compilemessages` for the new preset label.

Delivered component by component, confirming each before moving on.

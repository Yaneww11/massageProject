# RenkArt Site Import — Research Notes

**Date gathered:** 2026-07-20
**Source:** https://renkart.net (pages: index.php, about.php, prices.php, news.php, contact.php)
**Purpose:** Raw material for a future `brand-seed.json` (per the white-label platform
design, `docs/superpowers/specs/2026-07-19-white-label-platform-design.md`, Part 3 —
"Site import is a manual assisted process in a Claude session producing a
brand-seed.json"). Nothing in this file has been loaded into any database yet;
Part 2 (SiteConfiguration) and Part 3 (new-brand.sh) must exist first.

## Business identity

- **Brand:** RenkArt
- **Owner/sole specialist:** Reneta Kirilova ("Reni" to friends) — portrait and
  art/fine-art photographer, Stara Zagora, Bulgaria.
- **Business type:** solo portrait/art photography studio — **not** a massage/spa
  business. One person, one "specialist" record.
- **Bio (paraphrased from about.php "За мен"):** Reneta studied fine arts
  (painting), taught visual arts for 7 years, and has pursued photography
  seriously since living in Italy (2008–2012). She favors black-and-white and
  color portrait/art photography, story-driven and emotive compositions, and
  often works in diptych form, including self-portraits. Full original
  Bulgarian text is at https://renkart.net/about.php if a verbatim/translated
  version is needed later.
- **Site language:** Bulgarian only (`lang="bg"`); no English version exists on
  the live site. All bg→en translation for the new site is new work, not a port.

## Contact info

- Address: гр. Стара Загора, ул. "Орфей" 3 (до Музикалното училище) — Stara
  Zagora, 3 Orpheus St. (near the Music School)
- Phone: 0896710264
- Email: art76@abv.bg
- Facebook: facebook.com/RenkArt (page id 298633930158072)
- No Instagram/TikTok found.
- No published standing working hours anywhere on the site (only a one-off
  note about a single Santa-photo event day). **Needs a placeholder + real
  confirmation from the client before go-live.**

## Services / pricing (from prices.php — evergreen catalog)

Three natural service groups:

1. **Портретни фотосесии (Portrait sessions)** — studio or outdoor,
   kids/family, priced by number of edited photos delivered:
   - Мини фотосесия в студио — 15 photos — 120 EUR
   - Мини фотосесия навън (outdoor) — 15 photos — 130 EUR
   - Extra photo beyond package — 10 EUR/photo (incl. one 10×15cm print)
   - Голям фотопакет — 35 photos — 220 EUR (+ gift 20×30cm art print)
   - Макси фотопакет — 50 photos — 280 EUR (+ gift 20×30cm art print)
   - Add-ons available on request: paper type (matte/glossy/art), USB copy
     (price depends on GB), custom photobook/craft album (price depends on
     type/page count)
   - Note: raw/unedited files are never delivered — only finished, edited photos.

2. **Fine Art фотосесии (Fine Art portraits)** — studio, plain background,
   inspired by classical portrait painting, large-format prints with frame:
   - 120 EUR for children / 140 EUR teens+adults (individual) / 160 EUR couples
     / 180 EUR families
   - Includes 10 edited photos + archive; extra photo 15 EUR
   - Макси пакет: 30 photos — 280 EUR (+ gift 20×30cm art print)

3. **Арт / Будоар фотосесии (Art/concept sessions)** — fully custom concept
   shoots (wardrobe, props, styling, location), 2–8 hours depending on concept.
   **No fixed price published — "by arrangement."** Needs a placeholder +
   client confirmation, same as working hours.

## Visual identity

- **Logo:** `images/logo33.jpg` (downloaded to scratchpad, 300×300, grayscale) —
  an ornate vintage-style circular monogram with scrollwork flourishes, a heart
  motif, and the handwritten wordmark "RenkArt :)". Grayscale/ink-style, no
  inherent brand color.
- **Site chrome (from rendered screenshots of about/prices/index):** a
  near-black (~#0d0d0d–#141414) fixed left sidebar holding the logo + nav +
  contact links, white/off-white main content area, plain gray sans-serif nav
  labels. The site itself is essentially monochrome — **all the color comes
  from the photography**, not from a chosen brand palette.
- **Photography style:** warm, painterly, fantastical/conceptual portrait work
  — moody lighting, rich saturated color grading, occasional black-and-white,
  fairy-tale/costume themes recurring in art sessions.
- **CSS file (`style.css`) is a generic multi-purpose theme** (references
  Revolution Slider, lightbox.js, FontAwesome) with a large unused utility
  color palette (theme "skin" swatches like #ea3556, #26afd1, #8e44ad,
  #19dd89, #edde45) — these are **not** RenkArt's chosen brand colors, just
  leftover theme scaffolding. Fonts referenced (Fira Sans, Open Sans, Raleway,
  Hind, Teko, Georgia) are likewise generic theme defaults, not a deliberate
  brand type choice.
- **Recommended re-theme direction** (for whenever Part 2/SiteConfiguration
  exists): near-black/white/warm-grey base + one muted accent (e.g. warm gold
  or blush) for links/buttons, since pure black-and-white read too flat for
  interactive elements. Current font pairing on this codebase (Playfair
  Display + Montserrat) already fits this look reasonably well and doesn't
  need to change.

## Confirmed downloadable real images

Only two images were reliably extractable via direct URL/network inspection:

- `https://renkart.net/images/logo33.jpg` — the logo
- `https://renkart.net/images/reneta.jpg` — Reneta's portrait (holding a camera)

The masonry portfolio galleries visible on index.php/about.php/prices.php (8+
distinct photos per page, thematically matched to each page) render correctly
in-browser but **resisted automated extraction** in this session — they
don't appear as plain `<img src>`, CSS `background-image`, `<svg>`, or
`<canvas>` content, and no additional image network requests were observed
even on repeated fresh navigations. This is likely a proprietary
anti-hotlinking gallery script. **Getting the other ~15-18 curated images
will require a manual approach at execution time** — e.g. right-click-save
per image in a real browser session, or a screen-crop/save workflow — rather
than scripted download.

## News / seasonal content (out of scope for now — future feature)

news.php contains extensive **seasonal marketing content that doesn't map to
any current model** (no News/Blog model exists in this codebase):

- Christmas 2025 themed family photo packages (multiple price tiers by month/
  weekday-vs-weekend, in both BGN and EUR)
- A "Дядо Коледа" (Santa) mini photo-op package, one day only
- Christmas gift products: magnets, ornament photo baubles, calendars, craft
  photo albums, extra print sizes/prices
- Recurring **themed Art/concept sessions** used as recurring "collections":
  "Alice in Wonderland", "Snow Queen"/"Nutcracker" fairy-tale sessions,
  "Princess" boudoir-adjacent artistic sessions — each with its own props/
  wardrobe/backdrop description and sometimes its own date-limited pricing

This reads as an evergreen **pattern** (recurring seasonal/themed campaigns),
not a one-time thing — worth designing a real News/Post or Campaign model for
later, once you're ready to brainstorm/plan that feature. Not built now.

## Decisions already made in the brainstorming session (2026-07-20)

- Booking model: keep `Reservation`/`WorkingHours` as-is, but treat bookings
  as inquiry/requests rather than strict slot enforcement.
- Pull from all public pages (not just about.php).
- Real media reuse is authorized (Reneta is the client commissioning the new
  site).
- Separate Postgres DB per brand (not shared/multi-tenant) — matches the
  already-approved white-label Part 3 design.
- Re-theme only — keep current templates/layout, just change design tokens/
  SiteConfiguration values.
- Do **not** relabel massage-domain vocabulary in code (`verbose_name`s,
  admin labels, site titles stay as-is / become brand-configurable via
  Part 2's terminology fields instead).
- A few realistic demo reservations/comments are fine to seed (not real
  RenkArt customers).
- Next engineering step: implement Part 2 (`SiteConfiguration`) from the
  white-label design, planned via the writing-plans skill — **before**
  building any RenkArt-specific command or `brand-seed.json` tooling.

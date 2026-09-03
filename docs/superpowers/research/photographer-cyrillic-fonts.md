# Photographer-Site Google Font Pairs with Confirmed Cyrillic Support — Research Notes

**Date gathered:** 2026-09-03
**Source:** `https://fonts.google.com/metadata/fonts` (Google Fonts' own metadata API — the same
data that drives the "Language support" chips on each font's specimen page at
`fonts.google.com/specimen/<Font+Name>`), cross-checked against the Google Fonts `css2` API
naming conventions. Snapshot saved during this session at
`/tmp/claude-1000/.../scratchpad/gf_metadata.json` (2.7MB JSON, 1946 families) — not checked
into the repo, for reproducibility only; re-fetch the same URL to refresh.
**Purpose:** Ground `FONT_PAIRS` (in `massageProject/main_app/theme.py`) improvements/additions
for the RenkArt photographer-portfolio theming system (see
`docs/superpowers/research/renkart-site-import.md` for the brand: Reneta Kirilova, fine-art/
portrait photographer, Stara Zagora, Bulgaria — black-and-white and color portrait work,
diptychs, painterly/classical-portrait-painting sensibility). Site language is bg/en, so every
recommended font **must** render full Bulgarian Cyrillic, not just Latin.

## Method

`fonts.google.com/metadata/fonts` returns, per family, a `subsets` array (e.g.
`["menu","cyrillic","cyrillic-ext","latin","latin-ext","vietnamese"]`) and, where applicable,
an `axes` array describing variable-font weight ranges. This is the exact same data source
`fonts.google.com/specimen/*` pages read to render their "Language support" section — the
specimen pages themselves are JS-rendered SPAs that don't expose this text to a static fetch,
so the metadata API was used directly as the primary source instead of screen-scraping the
specimen UI. A family only qualifies as "full Cyrillic support" here if its `subsets` array
contains `cyrillic` (the base Cyrillic subset covers the modern Bulgarian alphabet; `cyrillic-ext`
adds extra glyphs for other Slavic/Turkic languages and pre-reform Bulgarian, not required for
modern Bulgarian body copy).

Every `google_fonts_url` proposed below (see "Top 5") was then independently re-verified by
actually calling `fonts.googleapis.com/css2` with a real browser User-Agent (a bare `curl` gets
a stripped-down legacy CSS response from that endpoint) and counting the `/* cyrillic */` and
`/* cyrillic-ext */` comments in the returned stylesheet — one per generated `@font-face` block.
For all 5 pairs, every requested weight of every font came back HTTP 200 with a matching
`/* cyrillic */` face for every `/* latin */` face (i.e. Cyrillic is not just present at the
family level, it's present at each specific weight requested in the URL). This settles the
"Cyrillic subset only has a subset of weights" risk the task called out — none of the 5 pairs
below have that problem.

**General caveat that applies to every pair below and isn't visible in the metadata API at
all:** Bulgarian typographic convention traditionally uses slightly different (italic-derived)
lowercase shapes for в, г, д, и, к, л, п, т, ц, ш, щ compared to Russian forms, activated via
an OpenType `locl` (localized forms) feature keyed to the `bg` language tag. Google's metadata
only reports subset presence, not `locl` coverage, so this wasn't checked font-by-font — call
it out as a known unknown rather than a per-font verified fact. Any of the fonts below may
render Bulgarian with the (still fully legible, just less "traditionally Bulgarian") Russian-style
letterforms; if house style ever cares about this, it needs a manual visual check per font,
not a metadata query.

## Important side-finding: audit of the *current* `FONT_PAIRS` in `theme.py`

Checked while researching — useful context for whoever edits `theme.py` next:

| Pair (theme.py key) | Heading font | Body font | Verdict |
|---|---|---|---|
| `playfair_montserrat` | Playfair Display — `cyrillic` ✅ | Montserrat — `cyrillic`, `cyrillic-ext` ✅ | **Passes** — both fonts are Cyrillic-complete already. |
| `cormorant_lato` | Cormorant Garamond — `cyrillic`, `cyrillic-ext` ✅ | **Lato — `["menu","latin","latin-ext"]`, no Cyrillic subset at all** ❌ | **Fails.** Lato has zero Cyrillic glyphs; Bulgarian text in this pair would fall back to the browser's default serif/sans, breaking the theme. |
| `poppins_opensans` | **Poppins — `["menu","devanagari","latin","latin-ext"]`, no Cyrillic subset** ❌ | Open Sans — `cyrillic`, `cyrillic-ext` ✅ | **Fails.** Poppins has no Cyrillic glyphs (only Latin + Devanagari) — this is probably the most surprising finding, since Poppins is extremely popular and looks like it "should" support everything. |
| `merriweather_sourcesans` | Merriweather — `cyrillic`, `cyrillic-ext` ✅ | Source Sans 3 — `cyrillic`, `cyrillic-ext` ✅ | **Passes.** |
| `raleway_roboto` | Raleway — `cyrillic`, `cyrillic-ext` ✅ | Roboto — `cyrillic`, `cyrillic-ext` ✅ | **Passes.** |

So 3 of the 5 existing pairs are already fine; `cormorant_lato` and `poppins_opensans` are the
two that silently break on Bulgarian text and would need their body font swapped (Lato → any
Cyrillic sans; Poppins → any Cyrillic sans) if kept. That's a separate, smaller fix from the "top
5 artistic pairs" ask below — flagging it here since it's directly relevant, not applying it
(no code was touched, per the task).

## Top 5 new artistic font pairs (Cyrillic-complete, both fonts)

Selection criteria: an artistic/editorial/gallery-feel display or literary serif for headings
(the RenkArt brand leans classical-portrait-painting and fine-art, not generic startup-corporate),
paired with a clean, highly legible sans for body/UI text — every font below returned `cyrillic`
in its `subsets` from `fonts.google.com/metadata/fonts`, verified individually.

---

### 1. Yeseva One + PT Sans

- **Heading — Yeseva One**: `subsets: ["menu","cyrillic","cyrillic-ext","latin","latin-ext","vietnamese"]`. Specimen: `https://fonts.google.com/specimen/Yeseva+One`. Metadata source: `https://fonts.google.com/metadata/fonts` (family "Yeseva One").
- **Body — PT Sans**: `subsets: ["menu","cyrillic","cyrillic-ext","latin","latin-ext"]`. Specimen: `https://fonts.google.com/specimen/PT+Sans`.
- **Google Fonts URL**: `https://fonts.googleapis.com/css2?family=Yeseva+One&family=PT+Sans:wght@400;700&display=swap` (re-verified live: HTTP 200, 3/3 requested faces carry a `/* cyrillic */` block)
- **Drop-in `theme.py` entry**:
  ```python
  'yeseva_ptsans': {
      'google_fonts_url': (
          'https://fonts.googleapis.com/css2?family=Yeseva+One'
          '&family=PT+Sans:wght@400;700&display=swap'
      ),
      'heading_family': "'Yeseva One', serif",
      'body_family': "'PT Sans', sans-serif",
  },
  ```
- **Why it fits**: Yeseva One is a bold, high-contrast decorative serif with real weight and drama — it reads as a designed art/editorial wordmark rather than a body-copy font, good for a hero name/logotype treatment ("RenkArt") or big section headers over photography. PT Sans is designed by ParaType, a Russian type foundry that draws Cyrillic natively rather than transliterating Latin shapes onto it — the Bulgarian text will look authored, not adapted.
- **Caveat**: Yeseva One ships as a single static weight (400, no italic, no bold) — it has no `wght` axis in Google's metadata (`axes: []`), so emphasis has to come from size/color/spacing, never `font-weight: bold`. PT Sans is also static, offering only Regular/Bold (400/700) — no light or medium weight for finer body-text hierarchy.

---

### 2. Alegreya + Alegreya Sans

- **Heading — Alegreya**: `subsets: ["menu","cyrillic","cyrillic-ext","greek","greek-ext","latin","latin-ext","vietnamese"]`. Specimen: `https://fonts.google.com/specimen/Alegreya`. Variable font, `wght` axis 400–900.
- **Body — Alegreya Sans**: `subsets: ["menu","cyrillic","cyrillic-ext","greek","greek-ext","latin","latin-ext","vietnamese"]`. Specimen: `https://fonts.google.com/specimen/Alegreya+Sans`.
- **Google Fonts URL**: `https://fonts.googleapis.com/css2?family=Alegreya:wght@400;600;700&family=Alegreya+Sans:wght@400;700&display=swap` (re-verified live: HTTP 200, 5/5 requested faces carry a `/* cyrillic */` block)
- **Drop-in `theme.py` entry**:
  ```python
  'alegreya_alegreyasans': {
      'google_fonts_url': (
          'https://fonts.googleapis.com/css2?family=Alegreya:wght@400;600;700'
          '&family=Alegreya+Sans:wght@400;700&display=swap'
      ),
      'heading_family': "'Alegreya', serif",
      'body_family': "'Alegreya Sans', sans-serif",
  },
  ```
- **Why it fits**: Alegreya is a literary, calligraphic serif originally cut for long-form reading and film credits — it has a humanist, slightly hand-drawn warmth (sharp, calligraphic italics) that suits a photographer whose bio leans on painting training and "story-driven" portraiture. Alegreya Sans is its purpose-built sans sibling, so both fonts share the same underlying letterforms/proportions and the pairing never feels mismatched.
- **Caveat**: Alegreya's italic (used for pull-quotes/captions) is quite cursive/calligraphic in both Latin and Cyrillic — lovely for a short caption or attribution line, harder to read in long italic paragraphs. Alegreya Sans is a static font (no variable axis) with a slightly wider weight menu (100/300/400/500/700/800/900) than Alegreya itself.

---

### 3. Cormorant Garamond + PT Sans

- **Heading — Cormorant Garamond**: `subsets: ["menu","cyrillic","cyrillic-ext","latin","latin-ext","vietnamese"]`. Specimen: `https://fonts.google.com/specimen/Cormorant+Garamond`. Variable font, `wght` axis 300–700.
- **Body — PT Sans**: same as above, `cyrillic` ✅, `cyrillic-ext` ✅.
- **Google Fonts URL**: `https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;600;700&family=PT+Sans:wght@400;700&display=swap` (re-verified live: HTTP 200, 5/5 requested faces carry a `/* cyrillic */` block)
- **Drop-in `theme.py` entry**:
  ```python
  'cormorant_ptsans': {
      'google_fonts_url': (
          'https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;600;700'
          '&family=PT+Sans:wght@400;700&display=swap'
      ),
      'heading_family': "'Cormorant Garamond', serif",
      'body_family': "'PT Sans', sans-serif",
  },
  ```
- **Why it fits**: Cormorant Garamond is already one of `theme.py`'s existing heading choices (currently misfired with Lato as its body partner — see the audit table above) — it's a delicate, high-contrast Garamond revival with genuine editorial/fashion-magazine polish, well suited to fine-art portrait work. This pairing keeps that heading choice but swaps in a body font that actually has Cyrillic, fixing the existing `cormorant_lato` pair's silent Bulgarian-text failure.
- **Caveat**: Cormorant Garamond's hairline strokes get faint at small sizes — best reserved for large headings/pull-quotes (24px+), not body text or small UI labels. It's a swap-in replacement candidate for `cormorant_lato`'s body font rather than a wholly new heading choice.

---

### 4. Philosopher + Manrope

- **Heading — Philosopher**: `subsets: ["menu","cyrillic","cyrillic-ext","latin","latin-ext","vietnamese"]`. Specimen: `https://fonts.google.com/specimen/Philosopher`.
- **Body — Manrope**: `subsets: ["menu","cyrillic","cyrillic-ext","greek","latin","latin-ext","vietnamese"]`. Specimen: `https://fonts.google.com/specimen/Manrope`. Variable font, `wght` axis 200–800.
- **Google Fonts URL**: `https://fonts.googleapis.com/css2?family=Philosopher:wght@400;700&family=Manrope:wght@400;500;600;700&display=swap` (re-verified live: HTTP 200, 6/6 requested faces carry a `/* cyrillic */` block)
- **Drop-in `theme.py` entry**:
  ```python
  'philosopher_manrope': {
      'google_fonts_url': (
          'https://fonts.googleapis.com/css2?family=Philosopher:wght@400;700'
          '&family=Manrope:wght@400;500;600;700&display=swap'
      ),
      'heading_family': "'Philosopher', sans-serif",
      'body_family': "'Manrope', sans-serif",
  },
  ```
  Note: Google Fonts classifies Philosopher itself as **Sans Serif** (category confirmed via
  the same metadata API), despite its Art Nouveau serif-adjacent flourishes in the italic — use
  `sans-serif` as the generic fallback, not `serif`, or the browser fallback will look wrong.
- **Why it fits**: Philosopher is an Art Nouveau–flavored sans with flared, flourished italics — distinctive and "designed" in a way that reads as intentional art direction rather than a stock corporate typeface, good for a photographer's tagline/section titles. Manrope is a clean, modern geometric grotesque that keeps body text crisp and neutral so it doesn't compete with the heading's personality or the photography itself.
- **Caveat**: Philosopher is static with only Regular/Bold (400/700, each with a matching italic) — no in-between weights. Manrope has no italic style at all in any weight, so don't pair an italic heading treatment with italic body text in this combination.

---

### 5. Old Standard TT + Nunito Sans

- **Heading — Old Standard TT**: `subsets: ["menu","cyrillic","cyrillic-ext","latin","latin-ext","vietnamese"]`. Specimen: `https://fonts.google.com/specimen/Old+Standard+TT`.
- **Body — Nunito Sans**: `subsets: ["menu","cyrillic","cyrillic-ext","latin","latin-ext","vietnamese"]`. Specimen: `https://fonts.google.com/specimen/Nunito+Sans`. Variable font, `wght` axis 200–1000 (plus `opsz`, `wdth`, `YTLC` axes).
- **Google Fonts URL**: `https://fonts.googleapis.com/css2?family=Old+Standard+TT:wght@400;700&family=Nunito+Sans:wght@400;600;700&display=swap` (re-verified live: HTTP 200, 5/5 requested faces carry a `/* cyrillic */` block)
- **Drop-in `theme.py` entry**:
  ```python
  'oldstandard_nunitosans': {
      'google_fonts_url': (
          'https://fonts.googleapis.com/css2?family=Old+Standard+TT:wght@400;700'
          '&family=Nunito+Sans:wght@400;600;700&display=swap'
      ),
      'heading_family': "'Old Standard TT', serif",
      'body_family': "'Nunito Sans', sans-serif",
  },
  ```
- **Why it fits**: Old Standard TT is modeled on 19th-century scholarly book typefaces — an antique, academic-press serif that echoes RenkArt's "Fine Art" line (portraits explicitly inspired by classical portrait painting, large-format prints in frames). It reads as archival/gallery-label typography rather than a web-app font. Nunito Sans is a warm, rounded, highly legible grotesque that keeps body copy and UI approachable without fighting the heading's antique character.
- **Caveat**: Old Standard TT is static and only ships Regular, Italic, and Bold — no bold-italic — and its letterforms are fairly thin/delicate, so it's best used for section headers and pull-quotes rather than a large hero display size where a bolder face would have more presence.

---

## Fonts checked and excluded (Cyrillic-incomplete, for reference)

Confirmed **against the same metadata API** to lack a Cyrillic subset entirely — despite being
common "artistic/editorial" picks, none of these can be used for Bulgarian text:

- **Poppins** — `["menu","devanagari","latin","latin-ext"]` (already flagged above; currently the heading font in the existing `poppins_opensans` pair).
- **Lato** — `["menu","latin","latin-ext"]` (currently the body font in the existing `cormorant_lato` pair).
- **Josefin Sans** — `["menu","latin","latin-ext","vietnamese"]`.
- **Karla** — `["menu","latin","latin-ext"]`.
- **Cinzel** / **Cinzel Decorative** — `["menu","latin","latin-ext"]` (a shame — the inscriptional Roman-capitals look would otherwise suit a fine-art/gallery brand well).
- **Abril Fatface** — `["menu","latin","latin-ext"]`.
- **Marcellus** — `["menu","latin","latin-ext"]`.
- **Unna** — `["menu","latin","latin-ext"]`.
- **Bodoni Moda** — `["menu","latin","latin-ext","math","symbols"]`.
- **Fraunces** — `["menu","latin","latin-ext","vietnamese"]`.
- **Crimson Text** / **Crimson Pro** — `["menu","latin","latin-ext","vietnamese"]`.
- **Rufina**, **Della Respira**, **Italiana**, **Actor** — Latin-only.

## Other Cyrillic-complete candidates considered but not in the final 5

Kept here in case a 6th option is ever wanted:

- **Forum** — `cyrillic`, `cyrillic-ext` ✅. Roman-inscriptional capitals-only display face, very striking for a one-line hero title, but all-caps and single-weight (400) makes it too limited for general heading use across a whole site.
- **Prata** — `cyrillic`, `cyrillic-ext` ✅. Elegant thin display serif, single weight (400) only, no italic/bold at all — riskier to theme consistently than the picks above.
- **Tenor Sans** — `cyrillic` (no `cyrillic-ext`) ✅. Minimal geometric sans with a fashion-editorial feel; single weight (400) only.
- **Marck Script** / **Bad Script** — both Cyrillic-complete cursive/handwriting fonts; excluded as heading candidates because a script face is a much bigger departure from the current pairs' character and risks legibility issues at small sizes — worth a future look if the brand wants a "signature" accent font (e.g. for a logotype-style wordmark) rather than a body-adjacent heading font.
- **PT Serif**, **Vollkorn**, **EB Garamond**, **Spectral**, **Literata**, **Bitter** — all confirmed `cyrillic` ✅, all solid literary/editorial serifs, any could substitute for the serif heading in pairs 2, 3, or 5 above; left out of the top 5 only to keep the 5 picks visually distinct from one another rather than 3 variations on "elegant Cyrillic-complete serif."

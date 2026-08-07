# Client-Facing Product Overview — Design Spec

## Purpose

A single marketing-style document introducing the software to **prospective buyers** who are not technical. It sells the platform's capabilities and demonstrates, at a narrative level, how easy it is to go from an empty install to a live site. It is not an operator's manual and not a technical README.

## Audience & Tone

- Reader: someone evaluating whether to buy/license this platform for their own business (spa, photography studio, salon, garage, nail studio, etc.), not a developer.
- Tone: marketing copy — confident, benefit-led, plain language. No code, no file paths, no framework names (Django, etc. are never mentioned).
- Positioning: product is presented generically ("this platform" / "the system") — no brand name yet.

## Format

- Single Markdown file, written in **Bulgarian**.
- **Text-only** — no screenshots or embedded images in this pass. May be added later once the copy is approved.
- Output path: `docs/PRODUCT_OVERVIEW.bg.md`.

## Content Scope

**Detailed sections** (real explanation + why it matters to a business owner):
1. Booking engine — real-time per-staff availability, working-hours awareness, double-booking/lead-time protection, client-facing upcoming/past reservations with edit/cancel window.
2. Theming & terminology system — colors/fonts/layout style/hero banner swappable without touching code; site vocabulary (e.g. "specialist" → "photographer"/"barber"/"mechanic") is editable; whole features (booking, reviews, Google sign-in) can be toggled on/off.
3. Client photo-proofing workflow — private per-reservation gallery, client marks favorite photos, leaves comments, tags photos against a labeled quota (e.g. "5 for print"), previews are watermarked until the client finalizes their picks.

**Brief-mention-only items** (one line each, no elaboration): portfolio/gallery pages with homepage carousel, client reviews with moderation, secure accounts including optional "Sign in with Google", admin dashboard, built-in bilingual support (Bulgarian/English), staff profile pages.

**Explicitly excluded from the document:** any framework/technology names, actual admin UI screenshots, terminal commands, database/migration steps, pricing, and any current real client's specific branding.

## Reusability Framing

The document must establish early (before the deep-dive sections) that the platform is generic across service verticals, not massage-specific — with a bullet list of example business types (wellness/spa, photography studio, hair salon, auto garage, nail studio).

## Structure

1. **Hook** — one-line pitch.
2. **What this is** — 2–3 sentence positioning statement.
3. **"Built for any service business"** — vertical examples list, placed early.
4. **Core capabilities** — the three detailed sections above.
5. **Also included** — the brief-mention list.
6. **From empty to live — a walkthrough** — non-technical, narrative-only setup story framed as configuring a *photography studio* (the "photo gallery" example from the original request): business basics → pick a look → name your world → add your team → build galleries → turn on booking → go live → clients review their proofs. Closes with an explicit statement that swapping vocabulary/roles turns the same steps into a hair salon, garage, or nail-studio setup — this is where the multi-vertical promise is reinforced concretely.
7. **Closing** — generic "interested? get in touch" call to action, no real contact details filled in yet.

## Out of Scope for This Pass

- English translation (may follow as a separate file later).
- Screenshots/visual mockups.
- Real product name, contact details, or pricing.
- A technical appendix for developers (not requested).

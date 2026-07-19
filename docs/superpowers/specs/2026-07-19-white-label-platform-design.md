# White-Label Platform Design

**Date:** 2026-07-19
**Status:** Approved design, pending implementation planning

## Goal

Turn the massage-studio booking site into a white-label product for Bulgarian
small service businesses (hair salons, photo studios, …). A new brand is
created by deploying a fresh instance and configuring branding, theme,
terminology, and feature toggles from the Django admin — no code changes per
brand.

## Decisions (agreed with the owner)

- **Same booking engine everywhere.** Business types differ only by
  branding, wording, theme, and per-brand feature toggles. No structurally
  different booking flows.
- **Scale:** 5–20 brands over time, all deployed and managed by the owner.
- **Hosting:** one instance + one database per brand, all on a single cheap
  VPS (Hetzner-class). Multi-tenancy (shared DB) was considered and rejected:
  at this scale it buys nothing and risks cross-tenant data leaks; separate
  instances give full data isolation, independent upgrades, and trivial
  offboarding at the cost of ~150–250 MB RAM per brand.
- **Web server:** nginx on the host + certbot (owner preference over Caddy).
- **Neutral core with full rename:** models, fields, URLs, views, and
  templates are renamed to business-neutral terms. The `massageProject`
  package name **stays** (owner decision).
- **Terminology:** admin-editable per brand and per language
  (django-modeltranslation), on top of a neutral default.
- **Theme:** admin-configurable colors, curated font pairs, a corner/shadow
  style preset, and a homepage hero layout variant.
- **Feature flags:** online booking, comments, Google login — each on/off per
  brand.
- **Market:** all brands are Bulgarian. Phone validation
  (`^(\+359|0)?8[789]\d{7}$`), bg-first/en-second languages, and
  Europe/Sofia stay hardcoded.
- **Site import** (taking texts/colors from a client's existing site) is a
  manual assisted process in a Claude session producing a `brand-seed.json`;
  no scraper code is built.
- **Provisioning:** a `new-brand.sh` script + admin polish; no control panel.
- **No production data exists yet** — migrations need not preserve any
  deployed database.

## Architecture Overview

Three sequential, independently verifiable parts, each with its own
implementation plan:

1. **Part 1 — Neutralization.** Pure rename refactor; site behavior and
   appearance unchanged.
2. **Part 2 — Brand configuration.** New `SiteConfiguration` singleton:
   theme, terminology, feature flags; template/view integration.
3. **Part 3 — Deployment platform.** Docker image, per-brand compose + env,
   nginx/certbot, provisioning and deploy scripts, runbook.

---

## Part 1 — Neutralization

**Goal:** no massage-specific identifiers remain in code; the site looks and
behaves exactly as today. No new features. User-visible wording ("Масажи",
"Терапевти") is deliberately *not* changed in this part — that is Part 2's
terminology system. This keeps Part 1 mechanically verifiable.

### Rename map

| Current | New |
|---|---|
| `Massage` model | `Service` |
| `Masseur` model | `Specialist` |
| `MessageReservation` model | `Reservation` |
| `MessageStudio` model | `BusinessInfo` |
| `StudioWorkingHours` model | `BusinessWorkingHours` |
| `WorkingHours.masseur` FK | `WorkingHours.specialist` (model name stays) |
| FK/fields `reservation.massage`, `.masseur` | `reservation.service`, `.specialist` |
| Views `MassagesDashboard`, `MassageDetail` | `ServicesDashboard`, `ServiceDetail` |
| URLs `/massages/`, `/massage/<pk>/` | `/services/`, `/service/<pk>/` |
| URL names `massages_dashboard`, `massage_detail` | `services_dashboard`, `service_detail` |
| Templates `massages_page.html`, `massage_detail.html` | `services_page.html`, `service_detail.html` |
| CSS class hooks referencing masseur/massage (e.g. `my_profile.css`) | neutral equivalents |

Already neutral, unchanged: `ServiceGroup`, `Gallery`/`Image`/`GalleryImage`,
`GalleryAlbum`/`AlbumPhoto`, `HomePage`, `Comment`, `WorkingHours` (model
name).

Renames propagate to: admin registrations, forms, mixins, signals,
`translation.py`, `populate_db`, `check_availability`, the
`view_all_reservations` permission, template variables, JS that touches
renamed endpoints/fields, and all tests.

### Migrations

`makemigrations` generates `RenameModel`/`RenameField` operations on top of
the existing history. Local dev databases migrate in place; nothing is
deployed, so no further migration-safety work is needed.

### Verification

- Full test suite green before and after.
- `populate_db` runs cleanly.
- Manual smoke: every page renders identically (only the two URL paths
  differ, acceptable pre-launch).

---

## Part 2 — Brand Configuration

### 2a. `SiteConfiguration` model

One new singleton in `main_app`, following the `HomePage` pattern
(`get_solo()`, pk=1, save-guard). It holds everything brand-configurable that
is not page *content* (content stays in `HomePage` / `BusinessInfo`).

**Theme fields**

- Seven color fields: `primary_color`, `primary_light_color`,
  `secondary_color`, `accent_color`, `background_color`, `text_color`,
  `text_muted_color`. `CharField` + hex validator, admin renders native
  color pickers. Defaults = the current spa palette, so the massage instance
  needs zero setup. Semantic `--success`/`--error` stay fixed in CSS.
- `font_pair`: choice among ~5 curated Google Fonts pairs — Playfair Display
  + Montserrat (current, default), Cormorant Garamond + Lato, Poppins + Open
  Sans, Merriweather + Source Sans 3, Raleway + Roboto. Each choice maps in
  one Python structure to a Google Fonts URL, a heading family, and a body
  family.
- `style_preset`: `soft` (current radii/shadows, default), `sharp` (minimal
  radii, flat shadows), `round` (pill buttons, large radii). Maps in Python
  to a dict of radius/shadow CSS variable values.
- `hero_variant`: `carousel` (current, default), `fullbleed`, `split`.

**Terminology fields**

`service_singular`, `service_plural`, `specialist_singular`,
`specialist_plural` — registered with django-modeltranslation so each gets
bg/en variants in the admin. Neutral defaults: "услуга/услуги",
"специалист/специалисти". The massage instance sets "масаж/масажи",
"терапевт/терапевти".

**Feature flags**

`booking_enabled`, `comments_enabled`, `google_login_enabled` — all
`BooleanField(default=True)`.

**Access & caching**

A context processor exposes the instance as `site_config` in every template.
`get_solo()` is cached (Django cache; `post_save` signal invalidates), so no
per-request query cost. Views import the same helper for flag checks.

**Admin**

One Unfold admin page ("Настройки на сайта") with fieldsets: Theme /
Typography & Style / Terminology / Features. Singleton: no add/delete.
New admin labels go through `makemessages` / `compilemessages`.

### 2b. Theming mechanics

- `base.html` keeps loading `variables.css` (defaults), then renders
  `partials/theme_overrides.html` — an inline `<style>` block that re-declares
  `:root` variables from `site_config`: the seven colors, the two font
  families, and the radius/shadow set from `style_preset`. Values are
  validated at save time (hex), so no escaping concerns.
- The hardcoded `@import` of Playfair/Montserrat moves out of
  `variables.css`; `base.html` renders a `<link>` to the selected pair's
  Google Fonts URL instead.
- Hero variants: the current carousel block in `home.html` is extracted to
  `partials/hero/carousel.html`; siblings `fullbleed.html` (first gallery
  image full-width, brand name + description overlaid, one CTA) and
  `split.html` (text column beside first gallery image) are added.
  `home.html` includes the selected partial via a small template tag. All
  variants consume existing `HomePage` data — no new content fields. Each
  variant gets its own CSS file under `staticfiles/css/components/`, styled
  only with theme variables. Hero CTAs respect `booking_enabled`.
- No live theme preview in v1: change in admin → save (cache invalidates) →
  refresh site.

### 2c. Terminology in templates

- Terms are used **only where they stand alone**: nav items, page titles,
  list headings (e.g. nav "Масажи" → `{{ site_config.service_plural|capfirst }}`).
- Action buttons and composed headings use generic phrasing with **no term
  interpolation**: "Запази час за масаж" → "Запази час". This sidesteps
  Bulgarian declension issues.
- Static strings without domain terms ("Адрес", "Работно време", "Вход")
  stay in the normal `.po` flow, untouched.
- Model `verbose_name`s stay fixed and neutral in the admin ("Услуги",
  "Специалисти") — the operator does not need per-brand admin wording.

### 2d. Feature flag enforcement (two layers each)

| Flag off | UI effect | Server enforcement |
|---|---|---|
| `booking_enabled` | Reserve buttons, booking nav, hero CTAs hidden; service detail is info-only; profile hides reservations section; auth modal CTA text falls back to generic | `ReservationPage`, `edit_reservation`, `delete_reservation`, `check_availability` return 404 via a `BookingEnabledMixin`/decorator |
| `comments_enabled` | Comments nav item, sections, and forms hidden | `AllCommentsView`, `submit_comment` return 404 |
| `google_login_enabled` | "Continue with Google" hidden in the auth modal | allauth `SocialAccountAdapter` guard (`is_open_for_signup`/`pre_social_login`) refuses Google auth, so direct URL access cannot bypass |

A brochure-only brand = `booking_enabled=False`: visitors browse services,
gallery, and contact info; auth remains available if comments are on.

### Part 2 testing

- Per flag: on → page works; off → 404 and UI element absent.
- Terminology: set custom terms, assert they appear in nav/titles.
- Theme: assert chosen hex values land in the rendered `<style>` block;
  assert font `<link>` matches the selected pair.
- Context-processor cache invalidation on save.
- i18n step per CLAUDE.md (`makemessages -l bg -l en`, translate,
  `compilemessages`) — many template strings are rewritten in this part.

---

## Part 3 — Deployment Platform

### VPS layout

One VPS (Hetzner CX22-class, ~€4–8/mo, upgradeable as brands grow):

```
/srv/brands/
  shared/
    docker-compose.base.yml     # anchors/defaults shared by all brands
    nginx/                      # one generated server block per brand
  relaxhealth/
    .env                        # SECRET_KEY, DB creds, domain, email, OAuth, Turnstile
    docker-compose.yml          # web container (shared image) + volumes
    media/                      # brand uploads (bind mount)
  <next-brand>/
    ...
```

- **One Docker image for all brands** (gunicorn + WhiteNoise for static),
  built from this repo. Brands differ only by `.env`, database, and media
  volume. Upgrade = build/pull one image, restart each container.
- **One Postgres server container**; one database + role per brand (data
  isolation without N Postgres servers). Nightly `pg_dump` per database +
  media rsync to off-site storage.
- **nginx on the host** (not containerized): one vhost per brand proxying to
  that brand's gunicorn port/socket. **certbot** (nginx plugin) issues and
  renews HTTPS per domain.
- **Media:** local disk on the VPS (bind mount). The Cloudinary dependency
  from the Render free-tier plan is not used for VPS deploys.
- **Per-brand externals** live in each `.env`: email credentials, Google
  OAuth client (one per domain, only if `google_login_enabled`), Turnstile
  keys.

### Scripts (deliverables)

- **`new-brand.sh <slug> <domain>`** — creates the brand directory, generates
  `.env` (fresh SECRET_KEY, DB password), creates the Postgres DB/role,
  writes `docker-compose.yml` and the nginx vhost from templates, runs
  certbot, starts the container, runs `migrate`, creates a superuser, and
  optionally loads `brand-seed.json` (initial `SiteConfiguration`,
  `BusinessInfo`, services) produced during an assisted site-import session.
  Target: ~10 minutes to a themed, running site.
- **`deploy-all.sh [slug]`** — builds/pulls the new image, then per brand
  sequentially: `migrate` + restart, stopping on first failure so a bad
  migration cannot damage every brand.
- **Runbook** in `docs/deploy/`: VPS bootstrap (Docker, nginx, certbot,
  firewall, backups) and disaster recovery.

### Part 3 verification

On a fresh Ubuntu VM: follow the runbook, run `new-brand.sh` twice, confirm
two isolated brands (separate DBs, domains, themes); make a trivial code
change and run `deploy-all.sh`; restore one brand from backup.

---

## New-brand workflow (end state)

1. Owner sends Claude a link to the client's existing site; assisted session
   extracts colors, texts, services → `brand-seed.json`.
2. `new-brand.sh <slug> <domain>` on the VPS → running, seeded instance.
3. Owner logs into that instance's admin: polish theme, terminology, flags,
   upload logo/photos, enter services and specialists' working hours.

## Out of scope (explicitly)

- Multi-tenancy / shared database, self-service signup, central dashboard
  across brands.
- Structurally different booking flows per business type.
- Non-Bulgarian markets (phone format, languages, timezone stay fixed).
- Automated site scraper/importer.
- Live theme preview; custom CSS override field; per-brand gallery toggle.
- Renaming the `massageProject` Django package.

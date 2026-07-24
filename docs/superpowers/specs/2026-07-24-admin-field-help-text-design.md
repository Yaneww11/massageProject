# Admin Field Help Text — Design Spec

Date: 2026-07-24

## Goal

The client owns the site and manages content through the Django admin, but
has no visibility into which admin field controls which part of the live
site. Add `help_text` to every `main_app` model field that renders on the
frontend, stating in plain language where it appears, so the client can
navigate the admin panel without guessing. Also codify a maintenance rule in
`CLAUDE.md` so this stays accurate as fields are added or reused in new
places.

## Scope

- **Models covered:** `main_app` only (`ServiceGroup`, `Service`,
  `Specialist`, `WorkingHours`, `BusinessInfo`, `Reservation`, `Gallery`,
  `Image`, `GalleryAlbum`, `AlbumPhoto`, `HomePage`, `BusinessWorkingHours`,
  `Comment`, `SiteConfiguration`). `accounts.CustomUser` is out of scope —
  different app/admin section, not part of this pass.
- **Fields touched:** only fields that actually render somewhere on the
  frontend (verified against templates below, not inferred). Structural FKs
  (`user`, `gallery`, `album`, `home_page`, `reservation`) and internal/audit
  fields (`updated_at`, `status_updated_by`, `status_updated_at`) are left
  untouched — no help_text added.
- **Style:** plain-language page/section descriptions only — no template
  file paths or code references. The audience is a non-technical site owner.
- **Existing help_text:** where a field already documents its format (e.g.
  `BusinessInfo.stats`/`credentials`/`faq` JSON shape, `main_image`'s aspect
  ratio guidance), the location sentence is **appended**, not a replacement.

## Verified field → help_text mapping

Each entry below was checked directly against the template(s) that render
it (not assumed) — see "Verification notes" for corrections found along the
way.

### ServiceGroup
- `name` → Shown as a category tab on the services page.
- `order` → Controls the order category tabs appear in on the services page.

### Service
- `name` → Shown on the homepage's featured services, the services page, the service detail page, and throughout the booking flow.
- `description` → Shown on the service detail page.
- `price` → Shown on the services page, the service detail page, and the homepage's featured services.
- `duration_in_minutes` → Shown on the services page, service detail page, and homepage's featured services; also used to calculate available booking time slots.
- `short_description` → Shown as the short teaser text on the homepage's featured services and on each service card on the services page.
- `image` → Shown on the services page card, homepage's featured services, and the service detail page. If left empty, a gradient placeholder is shown instead.
- `home_page` → When checked, this service appears in the "Featured services" section on the homepage (maximum 3).
- `group` → Determines which category tab this service is filed under on the services page.

### Specialist
- `name` → Shown on the booking page's specialist selector and on the customer's profile page (upcoming/past bookings).
- `description` → Shown as a short bio on the booking page's specialist selector.
- `image`, `phone_number`, `email` → not currently displayed anywhere on the site. **No help_text added** (nothing to point to).

### WorkingHours
- `start_time` / `end_time` → Not shown directly, but determines which time slots are offered to customers booking with this specialist on this day.
- `specialist`, `day_of_week` → left untouched (structural/choice fields, no standalone display).

### BusinessInfo
- `name` → Used as the alt text for the studio photo on the About page.
- `description` → Shown as the main body text on the About page.
- `main_image` → *(append to existing help_text)* "Shown as the hero photo on the About page."
- `address` → Shown on the customer profile page's contact card and the site footer.
- `phone` → Shown on the customer profile page and the site footer (as a tap-to-call link).
- `email_address` → Shown in the site footer as a mailto link.
- `facebook_link` / `instagram_link` / `tik_tok_link` → Shown as a social icon link in the site footer.
- `stats` → *(append)* "years_of_practice, clients_served, and certifications_count are shown as stat cards on the About page."
- `credentials` → *(append)* "Shown as the Trainings/Recognition section on the About page."
- `faq` → *(append)* "Shown as the FAQ accordion on the About page."

### Reservation
- `service` / `specialist` / `time` / `date` → Shown in the booking confirmation and on the customer's profile page bookings list.
- `status` → Determines whether the booking appears in the customer's upcoming or past bookings list (or is hidden entirely, if cancelled).
- `additional_text` → Shown to the customer when viewing, editing, or cancelling their booking.
- `user`, `updated_at`, `status_updated_at`, `status_updated_by` → left untouched (internal/audit fields).

### Gallery
- `title` → Shown as the small label above the homepage gallery section.
- `short_description` → Shown as the heading of the homepage gallery section.
- `images` → The first 3 images shown in the homepage gallery section.

### Image
- `image` → Shown in the homepage gallery section.
- `alt_text` → Used as the accessibility/alt text for this image in the homepage gallery section.

### GalleryAlbum
- `title` → Shown as the album title on the gallery page and the album's own page.
- `description` → Shown on the album's own page, and (for the first album only) on the gallery page tile.
- `slug` → Used to build this album's page URL.
- `order` → Controls the order albums appear in on the gallery page.

### AlbumPhoto
- `image` → Shown on the album's page, and — if it's the first photo — as the album's cover photo on the gallery page.
- `alt_text` → Used as the accessibility/alt text for this photo.
- `order` → Controls the order photos appear in within the album, and which photo is the cover (the first one).
- `album` → left untouched (structural FK).

### HomePage
- `brand_name` → Shown as the site name in the homepage hero, the header logo's alt text, the footer copyright line, and in emails sent to customers (booking codes, password resets).
- `description` → Shown as the subtitle text in the homepage hero.
- `logo` → Shown as the logo in the site header and in emails sent to customers.
- `privacy_policy_content` → Shown in full on the Privacy Policy page.
- `footer_tagline` → Shown as the tagline text in the site footer.
- `gallery` → left untouched (structural FK).

### BusinessWorkingHours
- `day_label` / `hours` → Shown in the "Working hours" list on the homepage and the customer profile page. *(`hours` keeps its existing note about leaving it empty for "Почивен ден"/Closed.)*
- `order` → Controls the order these rows appear in.
- `home_page` → left untouched.

### Comment
- `author` → Shown as the reviewer's name on the homepage reviews section and the full reviews page.
- `content` → Shown as the review text on the homepage reviews section and the full reviews page.
- `rating` → Shown as the star rating on the homepage reviews section.
- `is_reviewed` → Must be checked for this review to appear publicly on the homepage and the full reviews page.
- `created_at` → Shown as the review date on the full reviews page.
- `user`, `reservation` → left untouched.

### SiteConfiguration
- 8 color fields (`primary_color` … `border_color`) → Site-wide theme color, used across all pages.
- `font_pair` → Site-wide font choice, used across all pages.
- `style_preset` → Site-wide shape/shadow style (corners, buttons, cards), used across all pages.
- `hero_variant` → Controls which homepage hero layout is used.
- `service_singular` / `service_plural` → Used wherever the site refers to a "service" — e.g. the booking page and profile page.
- `specialist_singular` / `specialist_plural` → Used wherever the site refers to a "specialist" — e.g. the booking page and profile page.
- `booking_enabled` → When unchecked, hides all booking buttons/links site-wide (header, homepage, services page, service detail page, profile page).
- `comments_enabled` → When unchecked, hides the reviews section on the homepage.
- `google_login_enabled` → When unchecked, hides the "Sign in with Google" option in the login modal.

## Verification notes (corrections vs. initial draft)

- `Comment.rating` was believed to show on both the homepage and the full
  reviews page (`all_comments.html`); confirmed it **only** renders on the
  homepage — `all_comments.html` shows `author`/`content` but not stars.
- `HomePage.brand_name` and `HomePage.logo` were believed to only affect the
  header/footer/hero; confirmed they **also** flow into transactional
  emails (OTP, password reset) via `context_processors.py` →
  `templates/emails/base_email.html`. No other model's fields reach emails.
- `Specialist.image`, `phone_number`, `email` confirmed to have **zero**
  frontend rendering anywhere (grepped all templates) — no help_text added
  for these three.
- `GalleryAlbum.description` confirmed to render on the gallery page tile
  **only for the first album** (`{% if forloop.first and album.description %}`
  in `templates/pages/gallery.html`), matching the mapping above.

## CLAUDE.md rule (new subsection under "Frontend Conventions")

> **Admin help text** — every `main_app` model field that renders on the
> frontend has a `help_text` in `models.py` stating, in plain language,
> which page/section it appears on (no file paths — the admin user is a
> non-technical site owner). When you add a new field that will be shown on
> the frontend, or start using an existing field in a new frontend
> location, update its `help_text` to say so — append a sentence if the
> field already has help_text describing its format (e.g. the JSON fields
> on `BusinessInfo`), don't replace it. Structural FKs, audit/internal
> fields, and fields with no frontend rendering are left without this note.

## Implementation mechanics

1. Edit `help_text=_(...)` on the ~45 fields listed above in
   `massageProject/main_app/models.py`.
2. Run `makemigrations` — Django tracks `help_text` in a field's
   deconstructed state, so this is expected to produce a migration (no DB
   schema change, pure field-state bookkeeping). Include it if generated.
3. `makemessages -l bg -l en`; fill in `bg`/`en` `msgstr` for every new/
   changed `msgid`; `compilemessages`.
4. Add the CLAUDE.md rule above.
5. Run the full test suite (`python manage.py test`) to confirm the change
   is behavior-neutral.

## Out of scope

- `accounts.CustomUser` fields.
- Fields with no frontend rendering (left silently untouched — no
  "internal only" notes added, per decision).
- Any change to admin `list_display`, `fieldsets`, or layout — this is
  help_text only.

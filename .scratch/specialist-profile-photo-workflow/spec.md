Status: ready-for-agent

# Specialist Profile Table + Photographer Gallery Workflow

## Problem Statement

Specialists have no usable way to manage their own bookings from the site: their profile page shows only a read-only weekly calendar, with no filtering, searching, or sorting across their full reservation history.

On photographer-mode sites, the post-shoot workflow that exists is only half-built and only reachable through two disconnected Django admin screens. A specialist (photographer) can have a Proofing Gallery attached to a reservation and the client can review it and mark favorites — but nothing tells the client their gallery is ready, nothing tells the specialist the client has finished marking photos, the specialist has no way to see or download what the client marked, and there is no way at all to deliver the finished, edited photos back to the client. Every one of these steps today requires a staff member to work directly in Django admin.

## Solution

Replace the specialist/staff calendar with a filterable, searchable, sortable table of reservations, usable on both desktop and mobile.

On photographer-mode sites, build the missing half of the gallery workflow end to end: a specialist (or staff, on a specialist's behalf) uploads a Proofing Gallery from the front end instead of admin; the client is emailed when it's ready; once the client finalizes their marks, the specialist is emailed and gets a dedicated Marked Photos view with bulk ZIP and individual downloads of the originals; the specialist uploads a Final Gallery of edited photos; the client is emailed a secure link to it and sees it in their own profile under that reservation. A derived "phase" is shown consistently as a badge/filter wherever reservations are listed. None of this appears when the site isn't running in photographer mode.

## User Stories

1. As a specialist, I want to see a table of my reservations instead of only a calendar, so that I can search and filter my full booking history rather than only glancing at the current week.
2. As a specialist, I want to filter my reservations by status, date range, service, and client name, so that I can quickly find a specific booking.
3. As a specialist, I want my reservations sorted with the soonest upcoming booking first by default, so that I see what's next without extra clicks.
4. As a specialist, I want the reservations table to work well on my phone, so that I can check my schedule between appointments.
5. As staff with full access, I want the same table but covering every specialist, with an added filter to narrow to one specialist, so that I have one consistent view instead of the old calendar-plus-picker.
6. As a specialist or staff member, I want the reservations table to only show reservations I'm allowed to see, so that client data isn't exposed to the wrong person.
7. As a photographer, I want to upload a Proofing Gallery of many images and attach it to a specific reservation from my own profile, so that I no longer need admin access to hand off proofs to a client.
8. As a photographer, I want to set up the review labels (e.g. "prints") and how many photos a client may mark with each, at the same time I upload the gallery, so that the selection limit is configured without a separate admin step.
9. As staff, I want to upload a Proofing Gallery on behalf of a specialist who doesn't have a login account, so that every specialist's clients get the same experience regardless of whether that specialist can log in.
10. As a client, I want to receive an email when my photographer uploads my Proofing Gallery, so that I know to go review and mark my favorite photos.
11. As a client, I want my existing photo-review experience (marking favorites, applying labels, commenting, finalizing) to keep working exactly as it does today, so that this change doesn't disrupt something that already works.
12. As a photographer, I want to be emailed when a client finalizes their marked photos, so that I know it's my turn to start editing without having to keep checking.
13. As a photographer, I want a dedicated view per reservation showing exactly which photos the client marked as favorites, along with the labels and comments they attached, so that I know exactly what to edit.
14. As a photographer, I want to download all of a client's marked photos as a single ZIP, so that I can quickly pull the full-resolution originals into my editing software.
15. As a photographer, I want the option to download an individual marked photo instead of the whole ZIP, so that I have a fallback if I only need one or two images.
16. As staff, I want to view and download a client's marked photos on behalf of a specialist without a login account, so that they aren't blocked from the workflow.
17. As a photographer, I want to upload a Final Gallery of finished, edited photos to a specific reservation, so that I can deliver the completed work to the client.
18. As a photographer, I want the Final Gallery upload to accept my already-edited images without being rejected for size or cropped for display, so that the proofing-preview rules (built for a different purpose) don't get in my way.
19. As a client, I want to be emailed as soon as my final photos are uploaded, with a secure link to download them, so that I don't have to keep checking my account.
20. As a client, I want my final photos to also appear in my own profile under the relevant reservation, so that I can find them again later even if I lose the email.
21. As a client, I want the final-photo download link to work reliably regardless of how large the gallery is, so that a big wedding gallery doesn't fail to arrive because of an email attachment size limit.
22. As a specialist or staff member, I want a reservation's current stage in the photo workflow (e.g. gallery uploaded, awaiting client review, editing in progress, finals delivered) shown as a clear badge, so that I can tell what state any given booking is in at a glance.
23. As a specialist or staff member, I want to filter the reservations table by that same phase, so that I can find, for example, every reservation currently waiting on me to upload finals.
24. As a photographer, I want to only be able to upload a Final Gallery after the client has finalized their marks, so that I can't accidentally skip a step and deliver before I know what to edit.
25. As a photographer, I want the system to record the exact moment final photos were delivered automatically when the email goes out, so that I don't have to remember to mark it myself.
26. As a site owner running a non-photographer site, I want none of this photo workflow to appear anywhere — not in the specialist profile, not as email, not as a status badge — so that the site stays focused on plain bookings with no visible photography leftovers.
27. As a developer, I want the photo-workflow fields to exist in the schema regardless of photographer mode (matching how the existing Proofing Gallery fields already behave), so that toggling the flag on later doesn't require a fresh migration.
28. As a client, I want photos I've already marked and finalized to remain untouched even if my reservation's booking status later changes (e.g. gets marked no-show after the fact), so that a bookkeeping correction doesn't wipe out my photographer's work.
29. As a photographer, I want a soft-deleted (cancelled) reservation to disappear from my reservations table, so that a cancelled booking doesn't clutter my active work list, matching how deleted reservations already behave everywhere else in the site.

## Implementation Decisions

**Specialist/staff reservations table** (replaces `partials/specialist_calendar.html` entirely for both roles)
- One table component reused for both the `specialist` and `staff` branches of the existing role-based profile page; staff additionally get a specialist filter/picker in place of the old dropdown-that-swapped-the-whole-calendar.
- Filters: phase/status (see below), date range, service, client name search. Default sort: soonest upcoming first.
- Stat cards and the click-to-open detail modal from the old calendar are not carried over — the table's columns and filters replace that information directly.
- Fully gated by the existing view-level permission checks (`main_app.view_all_reservations`, `main_app.view_specialist_reservations`) already in place; no permission changes needed.

**Gallery model**
- Rename the existing `gallery_type` value `'reservation'` to `'proofing'` (data migration relabels existing rows; admin dropdown label text updated in both locales) so it reads clearly next to the new `'final'` type.
- Add a new `gallery_type` value, `'final'`.

**Image model**
- `Image.clean()`'s minimum-dimension and crop-position rules are skipped when the image's gallery is of the new `'final'` type — those rules exist for proofing-preview display and don't apply to already-edited deliverables. This deliberate skip is recorded in an ADR so it isn't mistaken for a missed validation later.

**Reservation model** — two new fields, no new enum:
- `final_gallery`: nullable one-to-one to `Gallery`, parallel to the existing Proofing Gallery field.
- `finals_delivered_at`: nullable timestamp, set automatically the instant the Final Delivery email sends successfully.
- New validation invariants alongside the existing `clean()` checks: `final_gallery` can only be set once the reservation's Proofing Gallery has been finalized; `finals_delivered_at` can only be set once `final_gallery` is set.
- No separate "gallery uploaded" or "finals uploaded" timestamp fields — the existing Proofing Gallery field and the new Final Gallery field being non-null are themselves the signal, matching how the existing Proofing Gallery field already works with no accompanying "uploaded at" field.
- None of this is enum-based; it follows the existing convention of plain boolean/timestamp flags used by the current Proofing Gallery fields.

**Derived phase** (display-only, computed, not stored — used for the table's badge and status filter; only computed/shown in photographer mode)
Priority order, highest first: finals delivered → final photos ready (uploaded, delivery pending) → editing in progress (client has finalized, no final gallery yet) → awaiting client review (gallery uploaded, review flag on) → gallery uploaded (transitional, before the review flag is set) → otherwise, just the reservation's plain booking status. This same derivation is used consistently everywhere a phase badge or filter appears.

**Front-end gallery-upload flow** (new — today this exists only as two disconnected Django admin screens)
- Reachable by the specialist themselves for their own reservations, and by staff on behalf of any specialist.
- In one flow: pick a reservation, upload the images (creates a Proofing Gallery of the existing type, attached to the reservation), and set up the review labels and their caps for that gallery (today this is only possible via an admin inline).
- Completing the upload automatically flips the existing "needs client review" flag on and triggers the client's "gallery ready" email — matching the existing automatic-vs-manual framing already used by the current Finalizing action.

**Specialist "Marked Photos" view** (new — nothing today lets a specialist see what a client marked)
- Per reservation, shows every image the client marked as a favorite during Photo Proofing, together with its attached review labels and comment — the same definition of "marked" already used by the existing Finalizing check.
- Offers a single ZIP download of all marked originals as the primary path, with individual per-image download links as a fallback.
- Reachable by the owning specialist or by staff on behalf of any specialist.
- Downloads are plain authenticated, ownership-checked access to the original files — no watermarking and no signed short-lived derivative generation, since that machinery exists specifically to deter piracy of unpurchased proofing previews and doesn't apply to a specialist downloading their own client's marked originals.

**Final Gallery upload + delivery** (new — nothing like this exists today)
- Specialist (or staff, on their behalf) uploads a Final Gallery to a reservation once the client has finalized their marks.
- On successful upload, the client is emailed a secure download link (not an attachment — galleries can be far larger than typical attachment limits), and the Final Gallery becomes visible in the client's own profile page under that reservation.
- The download link uses the same plain authenticated, ownership-checked access pattern as the Marked Photos downloads (not the watermarked/signed-derivative pattern used for live proofing preview), since finals are a one-time deliverable rather than a repeatedly re-viewed preview.
- `finals_delivered_at` is stamped automatically at the moment the delivery email sends successfully — no separate manual "mark as delivered" action.

**Notifications — email only** (no in-app notification system exists or is being built)
- A new general-purpose reservation/gallery email helper, following the same structure as the existing OTP email helper (render subject/text/HTML templates, send via the existing templated-email mechanism).
- Three triggers: gallery uploaded → client; client finalizes their marks → specialist (sent to the specialist's own contact email field, so it reaches specialists without a login account too); final gallery uploaded → client, with the secure download link.
- No reminder emails — there's no scheduling/cron infrastructure in the codebase to drive them, and adding one is out of scope.

**Photographer-mode gating**
- Every new field, view, and email trigger above is inert when the site isn't running in photographer mode, following the same pattern the existing Proofing Gallery fields and views already use — the schema and permissions don't change based on the mode, only what's rendered and what triggers fire.

**Translations**
- All new user-facing strings (table filter labels, upload-flow UI, Marked Photos view, new email subjects/bodies) need entries added to both locale files as part of this work, per the project's standing translation-update convention.

## Testing Decisions

A good test here exercises externally observable behavior — what a user can do, see, or receive — not internal call sequences. Two seams cover this feature:

- **Model-level tests**: exercise `Reservation`, `Gallery`, and `Image` directly (constructing instances, calling validation, saving) to check the new ordering invariants between the Proofing Gallery, Finalizing, the Final Gallery, and delivery; the `Image` validation skip for the final gallery type; and the derived phase logic across every priority-order case. This follows the same pattern already used by the existing photo-proofing test suite, which tests the current Proofing Gallery's model behavior (finalizing, unlocking, label-cap validation) directly rather than only through views.
- **HTTP-client-level tests**: exercise every new and changed view through the test client (making real requests against real URLs and asserting on responses, permissions, and rendered content) — the specialist/staff reservations table and its filters, the gallery-upload flow, the Marked Photos view and its downloads, and the Final Gallery upload and delivery flow. This matches the existing convention used by the current photo-proofing, gallery, and specialist-calendar test suites, which test ownership checks (a specialist or client can't reach another's data), permission checks, and response content this way rather than by calling view code directly.
- Email sends are asserted as a side effect of the relevant HTTP-client-level test (inspecting the test email outbox after triggering the action that should send one), not as a separate seam.
- No new test infrastructure is needed; both seams already exist in the codebase for the neighboring photo-proofing and gallery features.

## Out of Scope

- An in-app notification system (a notification model, bell/badge UI). Email is the only notification channel this covers.
- A `Service`-level default for the review-label selection cap. The existing fully-manual, per-gallery cap mechanism is kept exactly as it works today.
- Backfilling or provisioning login accounts for specialists who don't have one. The workflow is built assuming a logged-in specialist, with staff covering the gap for those who aren't.
- Reminder emails or any scheduled/cron-driven notification.
- A new reservation status enum. The phase is derived, not stored, and the underlying fields follow the existing boolean/timestamp convention.
- Any change to the existing client-facing Photo Proofing flow itself (marking, labeling, commenting, Finalizing), beyond triggering the new "client finalized their marks" email from the existing Finalizing action.

## Further Notes

- An ADR has already been recorded for reusing the Gallery/Image models for the Final Gallery rather than introducing a separate model, including the deliberate validation skip this implies.
- The project's domain glossary has already been extended with the new terms this feature introduces (Proofing Gallery, Final Gallery, Marked Photos, Final Delivery) to keep them distinct from the existing Photo Proofing vocabulary — in particular, "Marked Photos" is the correct term for what the specialist reviews; "selection" is an established anti-pattern term in this codebase's glossary and should not appear in code, UI copy, or future spec/issue text for this feature.
- While researching this feature it came up that the project's own documentation says `CustomUser` uses phone number as its login identifier, but the actual code uses email as the login identifier (and requires it). That's unrelated to this feature (if anything it simplifies the client-facing email notifications here) but is worth a correction at some point outside this spec's scope.

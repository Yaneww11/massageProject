# Spec: Login unreachable on mobile — nav overlay stays open and covers the auth modal

Status: done

## Problem

On a phone (viewport <= 940px), tapping **Вход / Login** in the mobile menu
appears to do nothing. The menu stays open, the login form never becomes
visible, and the page cannot be scrolled.

Below 940px the desktop user-menu login link is `display: none`
(`staticfiles/css/layout/header.css:588-593`), so the mobile overlay's trigger
is the **only** reachable login entry point. **Login is effectively unreachable
on mobile.**

## Reproduction (verified in Chrome, 2026-09-14)

Logged out, mobile width, on `/bg/`: open the hamburger, tap Вход. Measured
DOM/CSS state:

```
step1 (hamburger):   navOpen: true,   bodyOverflow: "hidden"
step2 (Login click): navStillOpen: true          <- nav never closes
                     modalOpened:  true          <- modal DID open
                     bodyScrollStillLocked: "hidden"
stacking:  .mobile-overlay      z-index 1200, background rgb(20,20,22) OPAQUE
           .auth-modal-overlay  z-index 1100
email input reachable?  ->  "NO - blocked by A.mobile-overlay__link"
```

Screenshot of the broken state: the nav fills the viewport; the modal is behind it.

## Root cause — three distinct defects

### D1. The nav is explicitly told not to close

`staticfiles/js/header.js:121-129`:
```js
overlay.querySelectorAll('a').forEach(function (link) {
    link.addEventListener('click', function () {
        // Auth-modal triggers stay put; they open a dialog of their own.
        if (link.hasAttribute('data-auth-modal-trigger')) return;
        closeOverlay();
    });
});
```
The comment assumed the dialog would paint above the overlay. It does not (D2).

Corroborating inconsistency: the booking CTA inside the same overlay
(`templates/partials/header.html:135-140`) uses `data-auth-modal-link`, which is
**not** exempted — so it already closes the nav and opens the modal correctly.
Two triggers in the same overlay behave differently; the exempted one is broken.

### D2. The modal loses the stacking comparison

- `.mobile-overlay` — `layout/header.css:404-411` — `z-index: 1200`, opaque
  `background-color: var(--bg-paper)`.
- `.auth-modal-overlay` — `components/auth-modal.css:4-16` — `z-index: 1100`.

Both are direct children of `<body>` (`header.html:95` and `base.html:33`) with
no intervening stacking context — verified: no `transform`, `filter`,
`opacity < 1`, `contain`, `isolation`, `will-change` or `backdrop-filter` on
`html`, `body` or `main`. So 1200 > 1100 is a direct, valid loss.

### D3. Body scroll stays locked

`openOverlay()` sets `document.body.style.overflow = 'hidden'` (`header.js:102`);
only `closeOverlay()` clears it (`header.js:111`). Because the nav never closes,
the modal is unscrollable — which matters on a short phone where the register
step does not fit on screen.

## Decisions

| # | Decision | Rationale |
|---|---|---|
| A1 | Clicking Login **closes the nav**, then opens the modal — delete the exemption at `header.js:125` | Fixes D1 and D3 with one deleted line (`closeOverlay()` clears the scroll lock). "Menu closes when you pick something from it" is what every other link in that overlay already does |
| A2 | Also raise `.auth-modal-overlay` above every other layer | Defence in depth. At 1100 it currently also loses to `photo_proofing.css` (1200 and 1210) — the same latent bug on another page |
| A3 | Do **not** introduce `--z-*` tokens in this spec | Correct long-term, but a cross-cutting refactor across 7 CSS files; bundling it turns a one-line fix into a risky sweep. Filed as follow-up below |
| A4 | **No automated regression test**; verify manually in Chrome | User's call. See Verification |

## Out of scope (flagged, not fixed)

- **z-index tokens.** Current values are ad-hoc across 7 files: 900, 999, 1000,
  1000, 1000, 1100, 1100, 1200, 1200, 1210 — `.user-menu-dropdown` and
  `.auth-modal-overlay` are both 1100. CLAUDE.md already forbids hardcoded
  colors for this same reason. Worth its own ticket.
- **`/accounts/login/` has no non-JS fallback.** `AuthEntryView` renders
  `templates/registration/auth_entry.html`, an empty shell whose only job is to
  call `window.AuthModal.open()`, with a `<noscript>` as the sole fallback. If JS
  fails there is no login form anywhere on the site. Real fragility, separate
  decision, not what was reported.
- **No automated test**, per A4 — this will not be caught by the suite if it
  regresses. Accepted knowingly.

## Work

1. `staticfiles/js/header.js:125` — remove the `data-auth-modal-trigger`
   early-return and its stale comment, so `closeOverlay()` runs for auth
   triggers like every other overlay link.
2. `staticfiles/css/components/auth-modal.css:4-16` — raise
   `.auth-modal-overlay`'s `z-index` above 1210 (the current site maximum, in
   `photo_proofing.css`).

Order matters: the click handler in `templates/partials/header.html:188-193`
already calls `e.preventDefault()` and does not `stopPropagation()`, so
header.js's overlay-link listener still fires — no change needed there.

## Verification (manual, Chrome, <= 940px viewport, logged out)

1. Open hamburger -> tap **Вход**: nav closes, login modal is visible and
   centred, email field focusable and typable.
2. Page scrolls while the modal is open (`document.body.style.overflow` is empty).
3. Dismiss the modal (X, backdrop click, Escape) -> returns to the page, not to
   an open nav.
4. Same for **Регистрация** (`header.html:157`) — same trigger attribute, same path.
5. The **Запазете час** CTA in the overlay still works as before (it was never broken).
6. Desktop (> 940px): user-menu Вход/Регистрация still open the modal.
7. Photo Proofing page: auth modal still layers correctly against the lightbox
   (1200/1210) — this is what A2 fixes.
8. `python manage.py test` still green.

## Translations

No new static strings. No `makemessages` pass required.

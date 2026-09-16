# Spec: Remove the PhotoLabel cap

Status: done — implemented in commit 4f72354 (2026-09-15). No tickets were cut; the spec landed as a single commit.

## Problem

`PhotoLabel.cap` limits how many Images a client may attach a given label to
during Photo Proofing. It encodes no business rule anybody relies on, and its
client-facing behaviour is poor: the limit is invisible until it silently
disables a chip.

Decision: **remove the concept entirely.** Labels become plain, uncapped
categories.

## What the investigation established

**There is no client-facing count of labelled photos.** The premise "remove the
count (e.g. 3/5)" does not match the code — no template, JS, or view ever
renders `cap` or a label tally as a number. `cap` reaches the browser only as an
invisible `data-cap` attribute (`photo_proofing.html:79`); `labelCounts` is
**never written to the DOM**. Its entire visible effect is:

```js
// photo_proofing.html:241-246
chip.disabled = finalized || (!active && labelCounts[key] >= labelCaps[key]);
```
styled by `staticfiles/css/pages/photo_proofing.css:435-438`
(`opacity: 0.45; cursor: not-allowed`).

The only cap *text* a client can ever see is a `window.alert`
(`photo_proofing.html:295`) surfacing `views.py:964`, and `:285` pre-blocks the
click — so it fires only on a race (second tab, or the cap filled concurrently).

**The `N / M` counters on the proofing page are unrelated and stay.**
`proof-header-count` (`:20`), `proof-marked-count` (`:94`),
`proof-finalize-summary-count` (`:111`) and the filter-tab counts (`:25/:28/:31`)
all count **marked photos**, driven by `refreshCounts()` (`:228-239`), which
never touches `labelCounts`/`labelCaps`. **Out of scope.**

**`cap` is never used to order, filter, or aggregate.** Exhaustive grep: it
appears in no `.filter()`, `.exclude()`, `.order_by()`, `.annotate()`,
`.aggregate()` or `F()`. `PhotoLabel` querysets always order by `order`
(`Meta.ordering`). Its only two runtime uses are the `MinValueValidator(1)` and
the plain comparison `current_count >= label.cap`.

**The specialist never sees it.** `marked_photos.html:28-31` renders label
*names* only; `MarkedPhotosView` (`views.py:480-489`) puts no caps or counts on
context.

**Seed data does not touch it.** Neither `populate_db.py` nor
`populate_renkart.py` references `PhotoLabel`, `cap`, or `ImageProof` at all.

## Decisions

| # | Decision | Rationale |
|---|---|---|
| E1 | Delete `PhotoLabel.cap` — field, validators, enforcement, form field, admin field, JS bookkeeping, error message and its translations | "Nobody uses it." A limit enforced but never explained is worse than no limit |
| E2 | Keep `PhotoLabel` itself | Labels are used and valuable — the specialist reads them in Marked Photos. Only the *cap* goes |
| E3 | The marked-photo counters stay | Different machinery, different concept, not what was asked |
| E4 | This spec owns all label-cap work; task 1 owns none | Explicit call to keep the two specs independently shippable. See Sequencing |

## Work

### Model + migration
1. `massageProject/main_app/models.py:849-856` — delete the `cap` field.
2. New migration: `RemoveField(model_name='photolabel', name='cap')`.
   **Destructive and not reversibly populated** — the column and its data are
   dropped. Accepted per "nobody uses it"; a reverse migration would restore the
   column but not the values.
   (Added by `migrations/0041_reservation_proofing_finalized_at_and_more.py:32`;
   no later migration touches it.)

### Server
3. `views.py:919-922` — drop `'cap': label.cap` from `labels_config`.
4. `views.py:958-966` (`toggle_photo_label`) — delete the `current_count` query
   and the 400 branch, so attaching a label is unconditional. This also removes
   a per-toggle COUNT query.
5. `views.py:428-430` (`ProofingGalleryUploadView.post`) — stop reading/writing
   `cap` when creating `PhotoLabel`s.

### Forms
6. `forms.py:143-172` — delete the `cap` field and simplify `clean()`: the
   `name and not cap` / `cap and not name` cross-validation goes; a row is
   simply a name or empty.

### Admin
7. `admin.py:244-247` — `PhotoLabelInline.fields` becomes `('name', 'order')`.

### Templates
8. `templates/pages/photo_proofing.html`:
   - `:79` — remove `data-cap="{{ label.cap }}"`.
   - `:214-222` — delete the `labelCaps` / `labelCounts` bootstrap.
   - `:241-246` — `refreshLabelChips()` reduces to `chip.disabled = finalized`.
   - `:281-296` — `toggleLabel()` drops the `labelCounts` guard and the two
     increment/decrement lines; keep the optimistic toggle and its rollback
     (the server can still fail for other reasons — verified: `_reject_if_finalized`
     (`views.py:888-891`) still returns a 403 `{'success': False, 'error': ...}`
     when the review was finalized between page load and the click, e.g. from a
     second tab or an admin lock. The rollback is reachable, not dead code).
   - Leave `refreshLabelChips()` call sites (`:268, :275, :478`) — it still
     handles the finalized state.
9. `templates/pages/proofing_gallery_upload.html`:
   - `:53-56` — delete the "Максимален брой" form group.
   - `:37-38` — reword the section blurb, which currently promises
     *"…и максималния брой снимки, които клиентът може да маркира с всеки."*

### Tests
10. `tests_photo_proofing.py` — delete `test_cap_must_be_at_least_one`
    (`:63-66`) and `test_label_toggle_respects_cap` (`:203-211`); drop `cap=`
    from fixtures at `:68-70`, `:81-82`, `:134`, `:180`.
11. `tests_proofing_gallery_upload.py` — drop `labels-{i}-cap` from the `_post`
    helper (`:98-104`); rewrite `test_labels_and_caps_are_created`
    (`:150-158`) to assert names and order only.
12. `tests_marked_photos.py:89` — drop `cap=5` from the fixture.

### Translations
13. These msgids become obsolete; remove them and re-run the CLAUDE.md pass
    (`makemessages -l bg -l en`, then `compilemessages`):
    - `"Максимален брой"` (`forms.py:150`, `models.py:851`,
      `proofing_gallery_upload.html:54`)
    - `"Въведете максимален брой за етикета \"%(name)s\"."` (`forms.py:160`)
    - `"Максимален брой снимки, които клиентът може да маркира с този етикет..."`
      (`models.py:853`, the `cap` help_text)
    - `"Достигнат е максималният брой за този етикет."` (`views.py:964`)
    - `"По избор: задайте етикети..."` (`proofing_gallery_upload.html:38`) —
      reworded, not deleted.

## Out of scope

- The marked-photo counters (E3).
- `docs/superpowers/plans/2026-07-28-photo-proofing-backend-plan.md:30,103,108,120-121`
  references `cap`. It is a historical plan document, not live documentation —
  left alone per CLAUDE.md's "don't delete pre-existing things you weren't asked to".

## Sequencing

Shares the `photo_proofing.html` label JS with
`.scratch/gallery-upload-scale/spec.md` (pagination). Landing **this spec first**
is cleaner: the cap machinery is gone before pagination arrives, so there is
nothing to reconcile. If pagination lands first, `labelCounts` is page-scoped and
label chips stop disabling correctly past page 1 until this spec lands.

## Verification

1. Proofing page: a label can be attached to every photo in the gallery — no
   chip ever greys out for a cap reason.
2. Chips still disable once the review is finalized.
3. Marked Photos still shows label names for the specialist.
4. Gallery upload: labels can be created with a name and no maximum; the form
   no longer rejects a name without a number.
5. Admin Gallery inline: label rows show name + order only.
6. `grep -rn "cap" massageProject/ templates/` returns no `PhotoLabel` hits
   (excluding `capfirst`, `stroke-linecap`, `caption`, `capacity`).
7. `python manage.py test` green, including the rewritten label tests.
8. Both locales compile with no obsolete `#~` entries for the removed msgids.

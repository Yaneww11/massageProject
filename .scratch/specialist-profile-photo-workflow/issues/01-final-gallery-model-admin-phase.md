# 01: Final Gallery model, admin support, and derived phase

**What to build:** The data foundation for photo delivery, verifiable entirely through Django admin before any new front-end exists. A staff member can create a Final Gallery, attach it to a reservation, and see the system refuse to let that happen out of order (before the client has finalized their marks, or before the Final Gallery itself exists for a delivery timestamp). Anywhere a reservation's photo-workflow stage needs to be shown, a single consistent "phase" value is available to derive it from.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] The existing gallery type used for client-facing proofing is renamed from "reservation" to "proofing" (existing rows relabeled by a data migration; admin dropdown text updated in both locales), so it reads clearly next to the new final-gallery type.
- [ ] A new gallery type for delivered, edited photos exists, distinct from the proofing type.
- [ ] A reservation can have a Final Gallery attached, independent of and in addition to its existing Proofing Gallery.
- [ ] A reservation can record the moment its Final Gallery was delivered to the client.
- [ ] Attaching a Final Gallery to a reservation is rejected unless that reservation's Proofing Gallery has already been finalized.
- [ ] Recording a delivery moment is rejected unless a Final Gallery is already attached.
- [ ] Images in a Final Gallery are not rejected for being too small or forced through the crop-position rule that applies to proofing-preview images — that rule is specific to live preview display and doesn't apply to already-edited deliverables.
- [ ] A single, consistently-ordered "phase" can be derived for any reservation (e.g. finals delivered / final photos ready / editing in progress / awaiting client review / gallery uploaded / plain booking status when no photo workflow has started) and is exposed for reuse by other views.
- [ ] All of the above is only meaningful when the site is running in photographer mode; on a non-photographer site the new fields exist in the schema but are never surfaced or required.
- [ ] Existing admin screens let a staff member exercise this entire flow (create both gallery types, attach each to a reservation, see the ordering rejected when done out of order, see the derived phase) without needing any new front-end page.
- [ ] The deliberate skip of the size/crop validation for the new gallery type is recorded as an architecture decision so a future reader doesn't mistake it for a missed check.
- [ ] Model-level tests cover: the ordering invariants (both rejection cases and the valid order), the validation skip for the new gallery type, and every case of the derived phase's priority order.

# 05: Final Gallery upload + delivery flow

**What to build:** Let a specialist upload the finished, edited photos for a reservation and deliver them to the client — by email with a secure link, and in the client's own profile — completing the end-to-end photo workflow.

**Blocked by:** 01 (Final Gallery model, admin support, and derived phase) for the schema/invariants; 04 (Marked Photos view) — extends the same email-helper module, and is the natural point in the workflow a specialist would have just finished editing from

**Status:** ready-for-agent

- [ ] A specialist can, from their own profile, upload a Final Gallery of finished images to a reservation whose client has already finalized their marks.
- [ ] Staff can carry out this upload on behalf of any specialist, including one without a login account.
- [ ] Attempting this before the client has finalized their marks is rejected, per the invariant established in ticket 01.
- [ ] On successful upload, the client is emailed a secure link to download their final photos — not an email attachment.
- [ ] The download link works reliably regardless of how large the gallery is.
- [ ] The moment of delivery is recorded automatically when that email sends successfully, with no separate manual step.
- [ ] The client's own profile shows the Final Gallery under the relevant reservation, so it remains findable without the email.
- [ ] The client can download their final photos through the same kind of secure, ownership-checked link used for the specialist's Marked Photos downloads (ticket 04), not the watermarked/expiring-preview mechanism used for live review.
- [ ] This entire flow, and the email it sends, only exists on a photographer-mode site.
- [ ] Test-client-level tests cover: uploading after finalization succeeds, uploading before finalization is rejected, staff uploading on behalf of a specialist, the client email being sent with a working secure link, the Final Gallery appearing in the client's profile, and ownership checks on the download itself.

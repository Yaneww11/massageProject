# 04: Specialist "Marked Photos" view + downloads + "marks finalized" email

**What to build:** Once a client finalizes their marked photos, tell the specialist by email and give them a dedicated per-reservation view of exactly what the client marked — with a bulk download of all of it, and individual downloads as a fallback.

**Blocked by:** 03 (Front-end Proofing Gallery upload flow) — extends the same new email-helper module; not a functional dependency, since a reservation can already reach the finalized state through the existing admin-driven path

**Status:** ready-for-agent

- [ ] When a client finalizes their marked photos on any reservation, the owning specialist is emailed that their client has submitted their marks.
- [ ] If the specialist has no login account, the notification still reaches them (sent to the specialist's own contact email, not to a login-linked address).
- [ ] A specialist can open a view, per reservation, listing every image the client marked as a favorite, together with the review labels and any comment attached to each.
- [ ] From that view, the specialist can download all of the marked images at once as a single archive.
- [ ] From that view, the specialist can also download any single marked image on its own.
- [ ] Downloads deliver the original uploaded files, not the watermarked preview shown to the client during review.
- [ ] Staff can view and download a specialist's Marked Photos on behalf of any specialist, including one without a login account.
- [ ] A specialist cannot view or download another specialist's Marked Photos.
- [ ] This entire view, and the email it's triggered by, only exists on a photographer-mode site.
- [ ] Test-client-level tests cover: the email firing on Finalizing with the right recipient, the view's content matching exactly what was marked (including labels/comments), both download paths, and ownership/permission boundaries (including staff-on-behalf-of access).

# 03: Front-end Proofing Gallery upload flow + "gallery ready" email

**What to build:** Let a specialist upload a Proofing Gallery to one of their own reservations directly from their profile, instead of needing Django admin — including setting up the review labels and per-label caps the client will use — and notify the client by email the moment it's ready to review.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] A specialist can, from their own profile, pick one of their reservations, upload multiple images, and have that become the reservation's Proofing Gallery.
- [ ] In the same flow, the specialist can define the review labels available on that gallery and the maximum number of images a client may mark with each.
- [ ] Staff can carry out this entire flow on behalf of any specialist, including a specialist without a login account.
- [ ] A specialist cannot upload a Proofing Gallery to a reservation that isn't theirs.
- [ ] Completing the upload automatically marks the reservation as needing client review, exactly as the existing admin-driven path already does.
- [ ] Completing the upload sends the client an email letting them know their gallery is ready to review, linking to the existing review page.
- [ ] This entire flow, and the email it sends, only exists on a photographer-mode site.
- [ ] This introduces the shared email-helper module (mirroring the structure of the existing one-off account email helper) that tickets 04 and 05 extend with their own notification triggers.
- [ ] Test-client-level tests cover: a specialist uploading to their own reservation, a specialist blocked from uploading to someone else's, staff uploading on behalf of a specialist (with and without a login account), the labels/caps being created correctly, and the client email being sent with the right recipient and content.

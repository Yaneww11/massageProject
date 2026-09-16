# massageProject

A booking site for a single-provider service business (massage/photography-style studios): clients book a Reservation with a Specialist, and afterwards may review photos from a Gallery tied to that Reservation.

## Language

**Photo Proofing**:
The client-facing review step after a Reservation whose Proofing Gallery is ready: the client marks favorite Images, attaches PhotoLabels, and leaves comments, then finalizes the review.
_Avoid_: photo review, gallery review (when specifically referring to this workflow)

**ImageProof**:
One client's proofing state for a single Image — whether it's marked as a favorite, its attached PhotoLabels, and any comment left on it.
_Avoid_: proof, selection

**PhotoLabel**:
A named category (e.g. "prints") a client can attach to Images during Photo Proofing, and which the specialist reads afterwards in Marked Photos. Any number of Images may carry a given label — labels sort the client's marks into groups, they do not ration them.
_Avoid_: tag, category

**Finalizing**:
The one-way action that closes Photo Proofing for a Reservation. Once finalized, the client can no longer change any ImageProof state; only an admin can unlock it to allow further changes.
_Avoid_: submitting, locking

**Proof Derivative**:
A signed, time-limited, watermarked copy of an Image shown to a client during Photo Proofing, tied to that specific client's identity. The original Image file is never served directly.
_Avoid_: preview, thumbnail

**Proofing Gallery**:
The Gallery attached to a Reservation (`Reservation.gallery`) that the client reviews during Photo Proofing. A Gallery only becomes a Proofing Gallery once it has been Published; before that it is a Draft Gallery.
_Avoid_: the gallery, reservation gallery

**Draft Gallery**:
A Gallery whose images are still being uploaded — not yet attached to its Reservation, and never seen by the client. Uploading hundreds of images takes many requests, so a Gallery exists in this state for minutes at a time, and can be abandoned and resumed. Becomes a Proofing Gallery or Final Gallery on Publishing.
_Avoid_: unfinished gallery, pending gallery, incomplete upload

**Publishing**:
The step that ends a Draft Gallery: it attaches the Gallery to its Reservation and notifies the client. Separate from uploading, and the only thing that emails the client — so a half-uploaded gallery never announces itself.
_Avoid_: finishing upload, completing the gallery

**Final Gallery**:
The Gallery attached to a Reservation (`Reservation.final_gallery`) holding the specialist's edited, delivered Images — created only after Finalizing, separate from the Proofing Gallery.
_Avoid_: edited photos, deliverables

**Marked Photos**:
The specialist-facing view of the Images a client marked as favorite during Photo Proofing (with their PhotoLabels and comments), shown once Finalizing has happened so the specialist can download them for editing.
_Avoid_: selections, picks, client selections

**Final Delivery**:
The one-way action of emailing the client a secure link to their Final Gallery once the specialist has uploaded it. Timestamped by `finals_delivered_at`.
_Avoid_: sending finals

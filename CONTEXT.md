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
A named, capped-count category (e.g. "prints") a client can attach to Images during Photo Proofing. Only a limited number of Images may carry a given label.
_Avoid_: tag, category

**Finalizing**:
The one-way action that closes Photo Proofing for a Reservation. Once finalized, the client can no longer change any ImageProof state; only an admin can unlock it to allow further changes.
_Avoid_: submitting, locking

**Proof Derivative**:
A signed, time-limited, watermarked copy of an Image shown to a client during Photo Proofing, tied to that specific client's identity. The original Image file is never served directly.
_Avoid_: preview, thumbnail

**Proofing Gallery**:
The Gallery attached to a Reservation (`Reservation.gallery`) that the client reviews during Photo Proofing.
_Avoid_: the gallery, reservation gallery

**Final Gallery**:
The Gallery attached to a Reservation (`Reservation.final_gallery`) holding the specialist's edited, delivered Images — created only after Finalizing, separate from the Proofing Gallery.
_Avoid_: edited photos, deliverables

**Marked Photos**:
The specialist-facing view of the Images a client marked as favorite during Photo Proofing (with their PhotoLabels and comments), shown once Finalizing has happened so the specialist can download them for editing.
_Avoid_: selections, picks, client selections

**Final Delivery**:
The one-way action of emailing the client a secure link to their Final Gallery once the specialist has uploaded it. Timestamped by `finals_delivered_at`.
_Avoid_: sending finals

# massageProject

A booking site for a single-provider service business (massage/photography-style studios): clients book a Reservation with a Specialist, and afterwards may review photos from a Gallery tied to that Reservation.

## Language

**Photo Proofing**:
The client-facing review step after a Reservation whose Gallery is ready: the client marks favorite Images, attaches PhotoLabels, and leaves comments, then finalizes the review.
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

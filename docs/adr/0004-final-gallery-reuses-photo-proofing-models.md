# Final Gallery reuses the Gallery/Image models, not a separate model

The photographer-delivered final images needed a home. We reuse the existing `Gallery`/`Image` models (new `gallery_type='final'`, plus `Reservation.final_gallery`) rather than introducing a separate, simpler model for delivered files.

This keeps GCS storage, WebP conversion, and the signed-URL delivery pattern already built for Photo Proofing, at the cost of `Image.clean()` needing a `gallery_type` branch: the `MIN_DIMENSION` and `crop_position` rules exist for proofing-preview display and don't apply to already-edited deliverables, so they're skipped for `gallery_type='final'`. A future reader seeing that branch should know it's deliberate, not a missed validation.

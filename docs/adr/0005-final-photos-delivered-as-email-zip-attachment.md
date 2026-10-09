# Final photos are delivered as a ZIP email attachment, not stored

Supersedes the final-gallery part of ADR 0004.

Final photos are no longer stored. The specialist uploads one `.zip` (at most `FINAL_ZIP_MAX_MB = 15`). Django validates it, attaches it byte for byte to the delivery email, and discards it after the request. `Reservation.finals_delivered_at` is the only stored trace. Staff or the assigned specialist can also set it by hand when photos were handed over another way. `Reservation.final_gallery` and `Gallery.TYPE_FINAL` are removed, along with the finals exception in `Image.clean()`. Existing final galleries are purged by `purge_final_galleries` before the migration that drops the field.

We chose this over keeping finals in GCS (the WebP gallery of ADR 0004, or a stored original ZIP behind a signed URL) for three reasons:
- typical deliveries are under 15 MB;
- the owner wants the client to receive untouched originals;
- the owner wants no files kept indefinitely in the bucket.

Trade-offs a future reader should know about:
- **Size:** deliveries over 15 MB cannot be sent. The limit sits below the 25 MB per-message limit that Gmail and many other recipients enforce, once the attachment's base64 overhead (about 33%) is counted. There is no splitting and no link fallback.
- **Lost emails:** nothing is kept, so a lost or bounced email means the specialist uploads the ZIP again. Re-sending is allowed and keeps the original `finals_delivered_at`. Bounces go to the sending Gmail inbox and are invisible to the site.
- **Sending path:** `GmailBackend` sends every message through the Gmail API upload endpoint (`message/rfc822` media upload, up to 35 MB) rather than a base64 `raw` JSON body. Google documents no size limit for the JSON-body route, and a message of about 20 MB would likely be rejected there.

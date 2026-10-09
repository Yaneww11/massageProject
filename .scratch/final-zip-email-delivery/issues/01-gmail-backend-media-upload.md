# 01: Send every email through the Gmail API upload endpoint

**Spec:** `../spec.md` (Decision 13, "`GmailBackend._send`"). **ADR:** `docs/adr/0005-final-photos-delivered-as-email-zip-attachment.md`.

**What to build:** Today `GmailBackend._send` (`massageProject/accounts/email_backend.py`) sends the message as base64 text (`raw`) inside the JSON request body. Google documents no size limit for that route, so a finals email of about 20 MB would likely be rejected with a 413. Change `_send` to send the MIME bytes (`email_message.message().as_bytes()`) through `media_body=MediaIoBaseUpload(BytesIO(...), mimetype='message/rfc822', resumable=True)` with `body={}`, and drop the base64 step. That endpoint accepts messages up to 35 MB. Error handling and `fail_silently` stay as they are. This changes how every site email is sent, so the existing email tests must stay green.

**Blocked by:** None (can start immediately).

**Status:** done

- [ ] With the Gmail service mocked, `messages().send` is called with a `media_body` of mimetype `message/rfc822` and with no `raw` key.
- [ ] The uploaded bytes match the message exactly, including any attachment.
- [ ] The existing email tests (OTP, reservation and proofing emails) all pass unchanged.
- [ ] `python manage.py test` has no new failures.

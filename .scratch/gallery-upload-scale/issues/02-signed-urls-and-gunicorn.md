# 02: Real 15-minute proof URLs and threaded gunicorn workers

**What to build:** Two deploy-side defects in the blast radius of this work.

First, watermarked client proofs are currently served with 24-hour signed URLs.
The code that was meant to produce 5-minute URLs calls the storage backend with
an argument the installed GCS backend does not accept, so it raises on every
single request and silently falls through to a branch whose comment claims it is
local-dev-only. Replace it with a signing helper that actually works against the
installed backend and produces a 15-minute URL. Scope the helper to the proofing
path — changing the global expiration setting would also reshape public
marketing image URLs.

Second, gunicorn has never been configured; it runs on defaults (2 sync workers,
1 thread each, 30 s timeout). Switch all three launch paths to threaded workers
with a 60 s timeout. This helps the read side, where requests genuinely block on
GCS. It does not speed up uploads, which are CPU-bound and hold the GIL.

**Blocked by:** None (can start immediately).

**Status:** done

- [ ] Opening a proofing gallery produces signed image URLs that expire in 15
      minutes
- [ ] No "storage backend does not support expiring URLs" warning appears in the
      logs when proof images are served
- [ ] Public marketing image URLs are unchanged
- [ ] All three launch paths start gunicorn with threaded workers, 4 threads, and
      a 60 s timeout; the running process reflects it
- [ ] `python manage.py test` is green

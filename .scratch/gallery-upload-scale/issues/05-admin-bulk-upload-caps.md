# 05: Caps on the admin bulk upload

**What to build:** Album and homepage galleries are curated in the admin, so the
50-image cap has to be enforced there or it does not exist. A 400-slide homepage
carousel is a bug, not a feature.

The admin bulk image upload refuses a selection that would push a gallery past
its cap — 50 for album and homepage, 400 for proofing and final — with a clear
error and no partial write. The form also carries a visible note telling the
admin to upload roughly 20 at a time, because the admin surface is not chunked
and a large single request will still time out.

The admin deliberately does **not** get chunked uploading. 400-image uploads
never happen on that surface; that is what the photographer workflow is for.

**Blocked by:** 03 (Draft galleries, chunked upload, and an explicit publish
step) — reuses the cap definition introduced there.

**Status:** done

- [ ] Adding a 51st image to an album or homepage gallery via the admin bulk
      action is a hard error with no partial write
- [ ] Adding a 401st image to a proofing or final gallery via the admin bulk
      action is likewise rejected
- [ ] The bulk upload form shows a note about uploading around 20 at a time
- [ ] The cap values come from the same definition ticket 03 introduced, not a
      second copy
- [ ] New strings are added to both translation catalogs and compiled per
      CLAUDE.md
- [ ] `python manage.py test` is green

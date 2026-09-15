# 04: Survive and resume an interrupted upload

**What to build:** A 400-image upload takes 10-15 minutes on production
hardware, so an interruption partway through is routine rather than exceptional.
It must not cost the photographer the whole session.

When a chunk fails, the browser retries it three times with backoff. If it still
fails, the upload **halts** and says how far it got ("uploaded 142 of 400,
resume later"). It does not skip the failed images and carry on — shipping a
silently incomplete gallery to a client is the one outcome that damages the
business.

The unpublished draft survives the interruption. The photographer finds it in a
list of their own unpublished drafts, reopens it, reselects the same folder, and
the upload resumes: images already in the draft are recognised by filename and
size and skipped rather than re-uploaded and re-converted. Publishing then works
exactly as in ticket 03.

Drafts are never auto-deleted. The photographer deletes an abandoned draft from
the draft list themselves; deleting a draft removes its images.

**Blocked by:** 03 (Draft galleries, chunked upload, and an explicit publish
step).

**Status:** done

- [ ] Killing the network mid-upload leaves a draft with a partial image count,
      not a lost gallery
- [ ] Resuming that draft skips the already-uploaded files and finishes; the
      final count has no duplicates
- [ ] A chunk failure is retried three times with backoff before the upload halts
- [ ] A halted upload reports how many of how many images landed
- [ ] The photographer can see their own unpublished drafts and delete one,
      which removes its images
- [ ] New strings are added to both translation catalogs and compiled per
      CLAUDE.md
- [ ] `python manage.py test` is green

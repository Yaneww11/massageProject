# 07: Serve thumbnails on the Marked Photos page

**What to build:** The specialist's Marked Photos page currently streams the
full-size 2560 px image through a worker for every single thumbnail on the page.
At 400 marked photos that is hundreds of megabytes of bandwidth and hundreds of
worker-seconds to render one page of thumbnails.

The page serves a small (~400 px) thumbnail instead, generated on first request
and cached thereafter, using the same caching approach already used elsewhere on
this path. These thumbnails are for the photographer, not the client, so they
carry no watermark. Thumbnails also load lazily.

The ZIP download path is unchanged and still delivers full-size images.

**Blocked by:** None (can start immediately).

**Status:** done

- [ ] The Marked Photos page serves ~400 px thumbnails, not full-size originals
- [ ] A thumbnail is generated once and served from cache on subsequent requests
- [ ] Thumbnails load lazily
- [ ] Thumbnails carry no watermark
- [ ] The ZIP download still contains full-size images
- [ ] `python manage.py test` is green

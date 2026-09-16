# 06: Paginate and lazy-load the client proofing page

**What to build:** Opening a 400-photo proofing gallery currently fires 400
concurrent image requests at two workers, each of which may have to decode the
source, composite a watermark, and write the result back to storage. The page is
effectively a self-inflicted denial of service.

The client sees 60 photos per page with working pagination, and images load
lazily as they scroll. The page stays responsive and the site stays responsive
while it is open. Selecting and labelling photos continues to work as it does
today within a page.

Lazy-loading alone is not enough — a fast scroll still stampedes both workers.
Pagination is what bounds the worst case.

The client-side label cap bookkeeping that would have broken under pagination
(it counted chips on the current page only) was already deleted in commit
4f72354, so there is nothing to reconcile. Confirm none of that machinery
survives before paginating.

**Blocked by:** None (can start immediately).

**Status:** done

- [ ] A 400-photo proofing gallery renders 60 photos per page with working
      pagination
- [ ] Photo images load lazily rather than all at once
- [ ] No page-scoped label-count machinery remains in the proofing template
- [ ] Selecting and labelling a photo still works on every page, including
      pages after the first
- [ ] Loading the page leaves workers available to serve other requests
- [ ] New strings are added to both translation catalogs and compiled per
      CLAUDE.md
- [ ] `python manage.py test` is green

## Notes

Pagination re-scoped everything the page counted from the DOM. Counts now come
from gallery-wide queries and move by delta; the filter bar moved server-side,
because filtering client-side would only ever reveal what is already on the
current page — the same page-scoping bug that sank the label caps.

# Reservations table pagination

Status: done

The staff/specialist reservations table on the profile page (`.reservations-table-section`) renders every matching reservation at once. Paginate it.

## Decisions (grilling session, 2026-10-09)

- **Ordering**: one continuous sequence — Upcoming Reservations soonest first, then Past Reservations newest first (both time-based, see CONTEXT.md) — cut into pages. Page 1 always starts at the soonest upcoming one.
- **Roles**: both staff and specialist (shared partial, shared code path).
- **Page size**: 15, fixed in code.
- **Controls**: Previous / "Page X of Y" / Next, plus a "Showing A–B of N" count.
- **Transport**: AJAX. The same `ProfilePage` URL returns only the rendered table partial when called with `X-Requested-With: XMLHttpRequest`; JS swaps `.reservations-table-section` with the returned HTML.
- **Filters**: also AJAX — submitting the filter form ("Филтрирай", or Enter) and the "Изчисти филтрите" link fetch and swap the section, resetting to page 1. No auto-filter on change.
- **URL**: `history.replaceState` to the fetched URL, so a refresh keeps the page/filters; Back still leaves the profile.
- **No-JS fallback**: pager links are real `?page=N&<filters>` hrefs; a full page load honours `?page=`.
- **Loading/errors/scroll**: dim the section and ignore clicks while loading; on fetch failure, navigate to the URL normally; after a swap, scroll the section into view only if its top is above the viewport.

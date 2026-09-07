# 02: Specialist/staff reservations table

**What to build:** Replace the read-only weekly calendar on the specialist and staff branches of the profile page with a filterable, sortable, searchable table of reservations, usable end to end on both desktop and mobile.

**Blocked by:** 01 (Final Gallery model, admin support, and derived phase) — needs the derived phase to power the status badge/filter

**Status:** ready-for-agent

- [ ] A specialist viewing their own profile sees a table of their reservations instead of the old calendar, with no stat cards or click-to-open modal carried over.
- [ ] Staff with full access see the same table covering every specialist's reservations, with an added filter to narrow to one specialist, replacing the old picker-plus-calendar.
- [ ] The table can be filtered by status/phase, by date range, by service, and by client name.
- [ ] On a photographer-mode site, the status/phase filter uses the reservation's derived phase (from ticket 01); on a non-photographer site it only offers the plain booking status, with no photo-workflow phases appearing anywhere.
- [ ] The table defaults to soonest-upcoming-first sorting.
- [ ] The table is usable and legible on a mobile-width screen.
- [ ] A specialist cannot see another specialist's reservations; a user without either permission cannot reach this view at all — existing permission checks continue to gate access exactly as before.
- [ ] Test-client-level tests cover: rendering for both the specialist and staff roles, each filter individually, the default sort, and that permission/ownership boundaries are enforced.

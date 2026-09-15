# 01: Unify the two gallery upload views onto a shared base

**What to build:** Nothing changes for the photographer. Proofing and final
gallery uploads behave exactly as they do today, but both views now run off a
single base that is parameterised by gallery type, the reservation field it
fills, whether a label formset is present, and which client email it sends.

This is a prefactor. Splitting each upload into create/chunk/publish (ticket 03)
means writing six endpoints instead of three if the duplication stays. The two
views are currently near-identical: scope resolution, reservation queryset,
per-file conversion loop, the "nothing uploaded" rollback, the reservation-save
rollback, and the success/warning messaging are all duplicated verbatim.

Keep the base to exactly what the two call sites need. No hooks, no registry, no
configurability beyond the four points of genuine variation.

**Blocked by:** None (can start immediately).

**Status:** done

- [ ] Both upload views produce byte-identical behaviour to before: same
      galleries created, same per-file error messages, same rollback on zero
      successful uploads, same emails, same redirects
- [ ] No duplicated conversion loop or rollback logic remains between the two
      views
- [ ] `python manage.py test` is green, with the same failure set as the
      pre-change baseline

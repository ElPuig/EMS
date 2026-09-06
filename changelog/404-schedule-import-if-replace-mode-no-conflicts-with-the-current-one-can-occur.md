# What's new:

## MP 3003/3004 can now mean different things in different cycles (CFGB vs PFI):
- The same official module code can be shared by two genuinely different subjects when they
  belong to different studies with different curricula - e.g. MP 3003 ("Tècniques
  administratives bàsiques") has different learning outcomes and a different internal/external
  hour split in the "Serveis Administratius" CFGB than in the "Auxiliar d'oficina" PFI. `ems.
  subject.code` used to be globally unique, which made this impossible without inventing a fake
  code suffix that would then no longer match the real code used by grade imports or a
  convalidation request. Replaced the global uniqueness rule with a narrower one: a duplicate
  code is only a real conflict when the two subjects could actually be confused for one another
  (either has no study assigned yet, or they share a study) - a code can be reused freely across
  two subjects that belong to entirely disjoint studies. Added the missing PFI AO subject data
  for MP 3003/3004 (with their own learning outcomes and hours, per the official curriculum) to
  the "Auxiliar d'oficina" cycle, which previously had no professional-module data at all for
  them. The teacher-schedule XML importer, which used to assume a module code always resolves to
  exactly one subject, now disambiguates by the entry's own group's study when a code is shared,
  the same way every other ambiguous match in that importer already refuses to guess instead of
  picking one arbitrarily.

# Fixes:

## Working schedules import no longer shows false conflicts when replacing a teacher's schedule:
- Importing a teacher's schedule in "replace" mode could wrongly flag a conflict against that same
  teacher's own existing sessions, even though that entire existing schedule is about to be
  overwritten regardless. Fixed so only genuine conflicts against a different teacher's schedule
  still require a decision. A second, related instance of the same false-positive was also found
  and fixed at the final import step itself (not just the review screen), where a real batch import
  in "replace" mode could still fail with a spurious overlap error naming several unrelated teachers.

## Manual group edits (rename, classroom reassignment) no longer reverted by the next upgrade:
- `data/custom/ems.group.csv` reseeds every listed column (course, acronym, level, study,
  classroom) on every upgrade, since a plain CSV can never carry `noupdate=True` in this Odoo
  version. That's the right contract for centre master config, but groups are living data an
  admin manages through the app during the year (renaming a group, reassigning its classroom,
  archiving it) - those edits were silently reverted by the very next `./upgrade.sh`. Fixed by
  freezing each group's own `ir_model_data` row (`noupdate=True`) right after every server
  start, once its file-seeded values have been applied for the first (and only) time - a
  brand-new group added to the file in a future version still gets created normally and is then
  frozen in turn. Verified end to end (manual DB edit survives a subsequent upgrade unchanged).
  A broader audit of which other `data/custom/` models have the same living-vs-master gap is
  tracked separately, not part of this fix.

# Changes:

## Clearer wording on the working schedules import wizard's "Existing schedule conflicts" step:
- Each conflict row now clearly labels which side is the new import and which is the existing
  database entry, with a clearer visual separator between them. The classroom pickers shown when
  reassigning a room now have their own column headers too, so it's clear which picker applies to
  which side.

# Internal changes:

## Release notes no longer hard-wrapped:
- `release-on-merge.yml` sourced the GitHub Release body from the merge commit's own message
  (`git log -1 --format=%b`), which GitHub's squash-merge textarea hard-wraps at ~72 characters
  when composing the merge commit. Fixed to read `github.event.pull_request.body` directly from
  the `pull_request: closed` event payload instead, since the plain PR description field doesn't
  get wrapped the same way regardless of merge strategy used.

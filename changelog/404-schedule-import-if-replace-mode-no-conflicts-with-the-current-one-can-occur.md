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

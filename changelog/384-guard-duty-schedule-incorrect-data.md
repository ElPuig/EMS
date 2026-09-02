# What's new:

## Choose whether a schedule import combines with or replaces a teacher's existing one:
- The working-schedule import wizard now asks, on its first screen, whether this import should
  combine with each teacher's current schedule (the default - nothing already there is lost unless
  this import also describes it) or replace it entirely (the file becomes that teacher's complete
  schedule, dropping anything else). Either way, anything this import genuinely does describe for a
  teacher always takes priority over what was there before.

# Fixes:

## Guard duty board no longer shows departed/reassigned teachers:
- A course transition retires a teacher's outgoing calendar once their teaching empties out, but
  left any remaining non-teaching commitment (a guard duty, a coordination meeting) still active
  on it forever - the Guard Duty Board, which reads across every teacher's calendar without
  checking whether its own calendar is archived, kept surfacing those stale entries indefinitely.
- Archiving a teacher's calendar now also archives its own remaining rows, and the board's own
  query adds an explicit check as well, so this can't silently regress again.

## Teachers no longer keep stale teaching assignments or tutor tags after a course transition:
- A teacher's "teaches this subject to this group" links (`ems.teaching`) were never resynced by
  a course transition at all - a teacher whose teaching moved on or ended kept showing the old
  assignment indefinitely, since neither the transition nor a later schedule import (which only
  ever adds, never removes) ever cleaned it up.
- A group's "Tutor" tag is itself backed by one of these same teaching links; once they're kept
  in sync with each teacher's actual calendar, a teacher who no longer tutors a group stops being
  shown as its tutor too - with no change to the group record itself, since groups are reused
  across academic years.
- A student left without a placement during a transition also stopped correctly clearing their
  old group's "Delegate" tag if they held it - now matches the same cleanup already applied to a
  student leaving the centre entirely.

## Schedule import: a self-conflict resolution could silently lose the winning side's calendar entry:
- When an imported file scheduled the same real teacher twice at the same time (recognised and
  resolved on the "File conflicts" step), the losing side's own removal could wipe the winning
  side's own calendar row too, right after it had just been written. The class/subject shown
  afterwards was correct, but the underlying weekly schedule silently wasn't.

# Internal changes:

## Migration for existing stale teaching/tutor/delegate data:
- A one-time data migration reconciles already-existing teachers/groups against the fixes above -
  archives leftover active calendar rows on already-archived calendars, resyncs every teacher's
  teaching links (including already-departed ones) from their real calendar, and clears any
  group's stale tutor/delegate reference that survived from before this fix.

## First step of a broader calendar-pipeline simplification:
- Course transition's own calendar-archival step used to find which weekly schedule line a
  migrating calendar block backs by matching its subject/group/time against existing records - a
  best-effort inference that predates a direct link between the two records added for exactly
  this purpose (2026-08-11) but never actually wired into this specific step. It now reads that
  direct link first, falling back to the old matching only for a calendar row old enough to
  predate it.
- Broader findings and a proposed further simplification of the whole calendar/schedule/teaching
  pipeline are written up in `plans/calendar_pipeline_simplification.md`. Investigating a further
  unification step surfaced the gap fixed above (the combine/replace choice) and, once that
  landed, let the schedule import wizard finally share the exact same reconciliation logic the
  manual schedule editor already used, instead of its own separate, near-duplicate version.

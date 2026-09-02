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

# Internal changes:

## Migration for existing stale teaching/tutor/delegate data:
- A one-time data migration to reconcile already-existing teachers/groups against the fixes above
  is drafted (`plans/course_transition_stale_teacher_assignments.md`) but not yet created -
  pending the developer's go-ahead on the next manifest version, since the current one is already
  tagged/released.

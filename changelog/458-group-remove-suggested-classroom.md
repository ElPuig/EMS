# Changes

## Group reference classroom set automatically from the schedule (suggested classroom removed):

- A group's reference classroom (`ems.group.space_id`) now follows its own schedule: the room of
  its tutorship (`subject_id.is_tutorship`) or, when the schedule has no tutorship (e.g. a
  reinforcement group), the room where it spends the most teaching hours. Recomputed whenever one
  of its schedule blocks is created, changed or removed, or a teacher's calendar is
  (un)archived, and once at the end of a working-schedules import.
- The automatic update never moves any class (only a manual edit does, as before, issue #405), and
  never clears the room of a group without a schedule, since the import wizard uses it as fallback.
- Removed the "suggested classroom" added for #405: the field, the form banner with its "Apply
  suggested classroom" button, the list column and the "Classroom drift" filter.
- No migration: existing groups are recomputed the next time their schedule changes.

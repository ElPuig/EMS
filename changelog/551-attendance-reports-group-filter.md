# Fixes

## Attendance reports group filter (students from other groups):
- The "Group" filter and group-by of the attendance reports pivot/graph used the session's groups
  (`ems.attendance_session_line.group_ids`): a session shared by several groups (e.g. IPO II for
  ASIX2A, ASIX2B, DAM2A, DAM2B and DAW2A) put every one of its students under each of them, so
  filtering by DAW2A listed ASIX/DAM students and per-group totals were inflated.
- New stored `student_group_id` on the session line: the student's main group when the roll-call
  is taken (depends on `student_id` only, so a later group change only moves the following
  roll-calls; a withdrawal keeps the earlier lines in their group). Odoo computes it for existing
  lines on upgrade from each student's current main group.
- The pivot's "Group" filter/group-by and the by-group PDF report now use it. The by-group PDF also
  includes a group's students in sessions of other groups (subjects taken with another group);
  access is unchanged (own sessions for a plain teacher, every session for the tutor scope), now
  shared with the by-student report in `_search_scoped_lines()`.
- The by-subject PDF report keeps selecting sessions by the session's groups.

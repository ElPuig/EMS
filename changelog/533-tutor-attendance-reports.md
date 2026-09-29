# What's new

## Attendance reports: tutors see every subject of their tutees:

- The Attendance → Reports screen (pivot/graph) shows a teacher's own subjects plus every subject of their
  tutees, whoever teaches it. It opens with a new, removable "My subjects" filter on by default, so the
  first view is still the teacher's own subjects; removing it shows all the tutees.
- The by-group PDF report offers the groups the user tutors (not only the ones they teach) and, for those
  groups, covers every subject. The by-subject PDF offers every subject taught in a tutored group and, for
  the tutored groups, covers every session of the subject. A plain teacher still gets only their own
  sessions, and a group outside the tutor scope is never widened.
- Follows the tutor chain of command (tutor_scope_user_ids): the department/seminar chief, head of studies
  and director above the tutor get the same view.
- Sessions of other teachers are read under a scoped sudo() inside the report wizard only, as the
  by-student report already did (#500); no new record rule, so the tutor's Attendance sessions screen is
  unchanged.

# Internal changes

## Current-course filter on attendance lines without going through the session:

- New stored field session_active on ems.attendance_session_line (related to the session's active flag).
  The Reports screen filters the current course on it instead of attendance_session_id.active, which
  applied the session's record rules and hid other teachers' sessions from tutors. Computed automatically
  for existing lines on upgrade.
- Tests: new tutor-scope fixture shared by the by-student, by-group/by-subject and pivot test classes, plus
  a tutor tour covering the default filter, pivot, graph and both PDFs.

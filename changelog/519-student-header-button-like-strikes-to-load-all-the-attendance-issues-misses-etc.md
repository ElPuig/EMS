# What's new

## Attendance button on the student's file (pivot filtered on that student):

- A new **Attendance** button in the student form's button box (next to Meetings/Relations) opens the
  attendance **Reports** pivot/graph screen already filtered on that student (a removable "Student"
  facet), so nobody has to go through Student's Attendances > Reports and search for them by hand.
- Same visibility and scope as the Reports menu (teacher, secretary, secretary admin; a plain teacher
  only reaches their own subjects, a tutor every subject of their tutees, Head of Studies/Secretariat the
  whole centre). Unlike the menu, the "My subjects" filter is not preselected, so a tutor sees every
  subject of the student at once.
- The Reports menu's server action now delegates to a shared
  `ems.attendance_session_line._get_reports_action()`, used by both entry points (no behavior change
  for the menu).
- Covered by new `TransactionCase` tests and a tutor-login tour (student form > button > pivot + graph);
  user manuals (teachers, tutors, secretary, head of studies; en/ca/es) gained a "From a student's file"
  section.

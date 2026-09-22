# Fixes

## Attendance report by student (access error for teachers, full report for tutors):

- Picking a student in the "By student" attendance report raised an access error for any teacher
  whenever that student also had sessions taught by another teacher: the From/To prefill read every
  session header of the student, but a teacher can only read their own sessions
  (`rule_attendance_session_teacher_own`), while session lines are readable by every teacher.
  Printing did not crash but silently kept only the teacher's own sessions.
- The by-student report now decides which sessions it covers in one place,
  `ems.attendance_report_wizard._get_student_lines()`, shared by the date prefill, `print()` and the
  PDF render: a plain teacher gets only their own sessions (same criterion as the by-group and
  by-subject reports); the student's tutor scope (`EmsBase.user_acts_as_tutor`, i.e. the tutor, the
  chiefs above them through `parent_id` and the Director) gets every session of that one student,
  whatever the subject or teacher, through a `sudo()` scoped to the wizard.
- The student dropdown also lists every tutee of the user, even when the user teaches them nothing.
- The PDF render no longer trusts the `status_ids` sent back by the client for the by-student
  report: it recomputes the lines from the wizard, so the `sudo()` path can't be used for another
  student by crafting the request.
- Tests: `TestAttendanceStudentReportScope` (plain teacher, tutor, chief above the tutor, crafted
  ids) and a new tour, `ems_attendance_report_student_scope`, run as a plain teacher and as a tutor
  who doesn't teach the student. Fixtures of `test_attendance_reports.py` moved to a shared
  `AttendanceReportCommon` base class.
- Docs: developer doc of attendance reports; teachers' and tutors' manuals (ca/es/en).

# Changes

## Attendance report PDFs named after the selected student, group or subject:

- The downloaded file of the 3 attendance report variants now carries the selected element after the
  report name, spaces as underscores (e.g. `Informe d'assistència_ per estudiant_Name_Surname.pdf`,
  `Informe d'assistència_ per grup_SMX1A.pdf`), so a teacher downloading several reports can tell them
  apart. The report name part stays translated to the user's language.
- To get there, the wizard prints on itself (`report_action(self)`, no `data`): with `data`, the web
  client downloads through the "particular report" route, which always uses `report.name` and ignores
  `print_report_name`. The 3 `ir.actions.report` now have `model = ems.attendance_report_wizard`,
  `print_report_name = object.get_report_filename()` and no binding.
- Side effect: the PDF of every variant (not only by-student) recomputes its lines from the wizard
  (`_get_report_lines()`), never from ids sent back by the client.
- Tests for the file name of the 3 variants (evaluated as the download controller does) and for the
  print action carrying the wizard as `active_ids` without `data`; user manuals (4 roles, ca/es/en).

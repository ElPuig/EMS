# Fixes

## Guidance can pick any student in the attendance PDF reports (issue #633):
- The attendance PDF report wizard narrowed its Group, Student and Subject dropdowns to the user's own
  teaching and tutor scope for everyone with an employee record, so Guidance (and Coexistence, Head of
  Studies and Director when they also teach) could not pick students they can already read on the
  attendance "Reports" screen. The wizard now uses the same "sees the whole centre" rule as that screen
  (ems.attendance_session_line._user_sees_whole_centre(): group_student_data_reader plus Secretariat),
  so both offer the same students.
- No sudo() needed for those users: their own domain_force=[] rules already let them read every session.

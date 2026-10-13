# Fixes

## Attendance reports for Guidance and Coexistence (whole centre):
- The attendance Reports screen (menu entry and the Attendance button on a student's file) narrowed the Guidance and Coexistence coordinators to their own teaching and tutees, so it opened empty for any other student although both posts read every student's attendance centre-wide. `ems.attendance_session_line._get_reports_action()` now treats every holder of `ems.group_student_data_reader` (Head of Studies and above, Guidance, Coexistence) as centre-wide, alongside Secretariat.

# Related with

- Closes #626

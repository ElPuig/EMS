# Fixes

## Attendance reports counted students removed from the roll-call:
- The attendance Reports screen opened from a student's file (Attendance button) counted the sessions the student had been removed from the roll-call of, so it showed a different absence rate than the same screen opened from Attendance → Reports (e.g. 15% against 0% for the same student and subject). The students' list runs with `active_test: False` and the button's result inherited it.
- Every attendance report now ignores archived lines whatever screen it is reached from: the Reports pivot/graph (`_get_reports_action()` forces `active_test` on), the three PDF reports and the attendance rate copied to the student's year record on graduation or withdrawal.

# Related with

- Closes #628

# Fixes

## Kiosk refused the check-out after an automatic check-in (stale last attendance):
- The automatic check-in taken when a teacher starts a roll-call ('current' mode) was stored with
  microseconds, a fraction of a second later than the "now" native hr.employee.last_attendance_id
  (a stored compute searching check_in <= now, depending only on attendance_ids) is computed
  against. It never became the teacher's last attendance, so the kiosk saw them as checked out
  and tried a second check-in instead of the check-out, rejected with "the employee hasn't
  checked out since...". Affected any teacher taking a roll-call before checking in at the kiosk,
  not only out-of-hours ones. 'start' mode could cause the same for a roll-call opened before the
  session starts.
- The automatic check-in is now stored without microseconds and capped at the current time.
- Migration 18.0.0.30.1 recomputes last_attendance_id for every employee whose stored value isn't
  their actual latest attendance.

## Automatic check-in only during the teacher's working hours:
- Taking a roll-call only checks the teacher in if it happens inside one of their expected working
  intervals for the day (their own timezone, approved absences subtracted, same helper as the
  auto-checkout). Out of hours (e.g. from home before the shift starts) the roll-call is recorded
  but no check-in is created. Teachers with no working schedule are never checked in
  automatically.
- Teacher manual ("Taking Attendance") and developer docs updated in all relevant languages.

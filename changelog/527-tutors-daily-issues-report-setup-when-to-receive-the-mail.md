# What's new

## Tutors choose when they receive the attendance issues report:
- New option in My Profile → Preferences → Notifications (`res.users.ems_attendance_report_moment`), only shown to whoever actually tutors a group (`ems_is_tutor`, from `ems.group.tutor_id`; not every holder of `ems.group_tutor`, which Department Chiefs, Heads of Studies and the Director also get). Four moments: when my working day ends (default, the previous behaviour), when my students' day ends (from each student's own enrollment-based schedule, so a 2nd-year student taking a 1st-year subject counts), when my next working day starts, and at a fixed time (`ems_attendance_report_time`, every school day of the centre).
- Discarded on purpose as too similar to another option: the group's end of day (misses students taking subjects in other groups), the centre's end and start of day (covered by "students' day ends" and "at a fixed time").
- Fallback when the moment can't be found (no working day, long leave, no classes): end of the centre's day (default schedule framework), then the company's `attendance_issue_tutor_default`, whose settings help now says so.
- Changing the preference moves the pending report to the new moment.
- Trilingual tutor manual `docs/{en,ca,es}/tutors/attendance-issues-report.md`; developer doc in `docs/en/developers/attendance/attendance_issue.md`.

# Changes

## "Request Allocation" button hidden from My Profile:
- The `hr_holidays` "Request Allocation" button in the My Profile header is hidden for everyone (EMS doesn't use employee-requested time-off allocations); "Request Time off" stays. View `ems.hr_holidays_res_users_view_form_allocation_hide`, covered by both My Profile tours.

# Fixes

## Attendance issues recorded after the tutor's report was sent were never reported:
- The tutor's report was one `queue.job` per tutor and day; once it had run, any later issue of that day (a late roll-call, a rectification) was added to the day's record but never emailed. Now each issue records whether it was reported (`ems.attendance_issue_status.tutor_notified`), there is a single pending report job per tutor shared by every day it covers, and each email lists every issue not reported yet, grouped by day and student. A report covering two days (next morning, fixed time) is one email.
- The old end-of-day calculation read the weekday in UTC and the raw schedule rows (ignoring absences and public holidays); it now uses the tutor's expected working day in the company's timezone.
- `migrations/18.0.0.32.0/post-migrate.py` marks every existing issue as reported except those whose report had not run yet, so the first report after the upgrade does not resend the whole course.

# Internal changes

## Shared working-day helpers:
- `hr.employee._ems_workday_intervals()` (own schedule, or the company's default framework) and `res.company._ems_default_framework_intervals()` extracted from the pending-tasks digest (#547) so the tutor report reuses them; `res.users._ems_workday_start()` now delegates to them. `res.partner._ems_teaching_attendances()` extracted from the student schedule compute.

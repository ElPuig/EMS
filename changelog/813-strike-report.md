# What's new:

## Staff walkout report for the Director (Absences > Reporting > Staff walkouts):
- New Director-only report (ems.staff_walkout_report, transient, + ems.staff_walkout_report.line) with the figures the Director reports to the Departament about every hour of a walkout day: a dialog to choose the day (today or a past day), then a pivot with one row per time slot already started and columns per staff type (teachers, administrative and services staff) and contract type (hr.contract.type: funcionari, interí...), measures "On walkout", "Not on walkout" (checked in or on a justified absence), "Expected to work" (= both) and "% on walkout"; drill-down to the names and the native xlsx download.
- Expected to work = an own schedule period already started. On walkout = no check-in at all that day, from their first started period not covered by an absence request approved or waiting for approval; cumulative. A late check-in takes them out entirely (the delay may be caused by the walkout). Refused/cancelled requests and detected absences are no justification. Vacancies are left out.
- The figures are computed once, on Show (reloading the pivot shows them again); today's title carries the time they were read at.
- Staff without their own schedule in EMS (resource.calendar.employee_id) do not appear: PAS need their schedule entered for the report to count them.

# Internal changes:

## Absence intervals shared between the guard duty board and the walkout report:
- ems.course._get_guard_duty_leave_intervals extracted from _get_guard_duty_absence_intervals (the absence requests part), reused by the new report.

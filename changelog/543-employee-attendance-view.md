# Breaking changes:

## Heads of Studies see and manage the attendance of their own branch only:
- A Head or Deputy Head of Studies no longer sees and edits every employee's check-ins centre-wide, nor decides any correction request: only those of their own branch, through the two ways somebody is theirs (developer's decision, 2026-10-11): the chain of command (everybody below them) and the area whose attendance they manage. The Director and the administrator keep the whole centre. Another branch's Head of Studies no longer even sees the request.
- A centre whose Heads of Studies must know at any time who is in can switch on the new setting "Heads of Studies see everybody's attendance (EMS)" (Employee Attendances > Configuration > Settings, off by default): they then read every employee's attendance; correcting it and deciding correction requests stay within their branch. After deploying, switch it on in the instances that need it.
- Technically: `ems.group_head_of_studies` now implies hr_attendance's Officer group instead of its Administrator one (whose native rule opens everything and cannot be narrowed by another rule), and `ems.group_director` implies the Administrator one. Migration `18.0.0.36.0` takes the Administrator group away from the users who only held it through the old implication (`res.users._ems_revoke_stale_attendance_admin()`); a user granted it by hand without being a Head of Studies keeps it. New rules `rule_hr_attendance_hos`, `rule_hr_attendance_hos_read_all` (toggled by the setting), `rule_attendance_correction_director`; `rule_attendance_correction_hos` narrowed.

# What's new:

## Department Chiefs see their department's attendance:
- A Department or Seminar Chief now sees, read-only, the check-ins of everybody below them in the hierarchy (new rule `rule_hr_attendance_department_chief`, on `tutor_scope_user_ids`); they used to see only their own.

## Past courses' staff attendance is archived:
- The staff's check-ins and check-outs get a real archive flag (`hr.attendance.active`). When a course transition switches the current course, everything from before the new course is archived (`hr.attendance._ems_archive_before_course()`), so lists and reports are about the course that starts; migration `18.0.0.36.0` archives what already belongs to past courses. Nothing is deleted: the new "Archived" filter shows them.

# Changes:

## The staff attendance list opens flat for an employee:
- Employee Attendances > Attendance > Overview used to open grouped by month and by employee for everybody. A plain employee, who only ever sees their own check-ins, now gets a flat list, so picking one to request a correction takes one click; from Department Chief up, who see several employees, the grouping stays. Done with groups on the search view's default group-bys (a default for a filter the user's groups do not include is ignored), so the action is the same for everybody.

# Internal changes:

## Version and tests:
- Manifest version raised to 18.0.0.36.0 (authorized by the developer) for the migration above.
- New TestEmployeeAttendanceAccess (every role, the setting, both flows of the correction requests, the list's filters per role, archiving, the group clean-up), two tests in TestCourseTransition, TestEmployeeRoleGroupSync adapted, new tours `ems_employee_attendance_list_employee` (as a teacher) and `ems_employee_attendance_list_chief`. ca/es translations; teacher, Head of Studies and course-transition manuals (3 languages); new developer doc `employees/employee_attendance.md`.

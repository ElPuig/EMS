# Fixes

## Auto check-out notice only reaches who can correct the attendance:
- When the automatic check-out could not use the scheduled hours and set the check-out to one hour after check-in, its "please review and correct" message also went to the employee's Department or Seminar Chief (`parent_id`), who can read their branch's attendance but cannot correct it.
- It now goes to the employee and to whoever actually corrects their attendance, resolved exactly like an attendance correction request is routed: the nearest Head or Deputy Head of Studies above them, else the manager of their area's attendance (`attendance_manager_id`), else the administrators. The resolution moved to a shared `hr.employee._find_attendance_approvers()`, used by both.
- The other auto check-out messages were already right: the normal closes only leave a chatter note, and an unexpected close failure schedules an activity for the administrators.

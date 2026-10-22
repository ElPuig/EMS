# Fixes

## Guard duty board: a co-taught lesson moves or is swapped with all its teachers:

- Issue #678. An internal arrangement plan (#645) moved a co-taught lesson with only one of its teachers: the other one stayed at the usual time, as if still teaching a lesson that was no longer there, and the planner thought the group still had a class then (dev DB case: AD2A's MP0664 on 2026-10-22, only Óscar Bagan moved to 16:00 while Gabriel Nicolau stayed at 19:20).
- The teachers who give a lesson together (same group or groups at the same time) are now a pack (`ems.course._arrangement_sessions()`): a move or a swap takes the lesson with all of them, one `ems.absence_cover` per teacher who moves it, all one decision (`_same_decision()`, `_with_siblings()`, `_decision_pack()`): withdrawn together, named together in the label ("B and C move their 11:00 lesson to 10:00."), allowed to share the class by `_check_one_guard_per_class`. A teacher away at the lesson still moves it to a gap where they are in, as before.
- When a co-teacher who is in at the lesson cannot follow it (busy or away in the gap, or their day would get longer), the plan is still offered with a warning per teacher saying why, ranked after the same arrangement with the whole pack (new planner criterion 5). Once applied they stay on guard at the lesson's usual time (`ems.absence_cover.stayed_employee_ids`): tagged "(lesson moved)" in the guard column (screen and PDF), offered as a guard for that period, told by message like the rest, and released from whatever they were sent to cover if the arrangement is withdrawn.
- On the absent side of a swap every teacher away from the class must be able to teach the other lesson, or the swap is not offered.
- The students' notice lists a co-taught lesson once.
- New tests in `TestAbsenceCoverage` (pack move, absent co-teacher, co-teacher left on guard and assigned, whole pack first, pack swap, absent side of a swap) and a new tour (`ems_absence_arrangement_co_teaching`). Board load timing unchanged on the dev DB (~0.12-0.17 s for the afternoon of 2026-10-22, before and after).

## Guard duty board: the week arrows no longer skip a day where the clocks change:

- Reported while testing #678: moving to the week of 26 October 2026 with the arrows showed Monday and Tuesday both as the 25th, and every tab one day early (only picking the date from the calendar worked). The arrows, the tabs and `mondayOf()` added days as 24-hour blocks of milliseconds, and the 25th of October has 25 hours, so the week started on Sunday at 23:00. They now count calendar days (`addDays()`); the 23-hour day in March, going back a week, had the same problem.
- New tour `ems_guard_duty_board_clock_change`, run with the test browser in Europe/Madrid (it runs in UTC otherwise, where there is no clock change): fails with the old code, passes now.

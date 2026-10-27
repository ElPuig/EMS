# Fixes

## Guard duty arrangements no longer change a teacher's entry or exit time when they swap a lesson with a duty:
- When an arrangement takes a teacher's lesson to an hour where they have a guard, a coordination or any other non-teaching duty, the duty now swaps to the hour the lesson leaves (`schedule_shift()`'s new `duties`, from `ems.course._duty_periods()`): the teacher's day is unchanged, so the proposal no longer says they come in later or leave earlier, and the ranking no longer counts it as a change. Only a lesson taken to an hour off their timetable changes their entry or exit time.
- A teacher's timetable cannot be changed without them: applying steps that change somebody's entry or exit time now asks first ("Working day changes: ... Have you talked to ...?"). "Not yet" applies nothing and keeps the dialog the plan came from open.
- Tests: `schedule_shift` unit test, updated chain assertions, the arrangement tours confirm (and once cancel) the new dialog. Teachers' guard-duty manual (ca/es/en) and developer doc updated, ca/es translations added.

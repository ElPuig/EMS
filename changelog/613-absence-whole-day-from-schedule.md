# Changes:

## Absences: times covering the whole timetable of the day are filed as a whole day (issue #613):
- Not coming in at all is always a whole day and counts the full working day (7.5 h), however
  many lessons there were. A request left as partial whose times go from the employee's first
  lesson of that day to the end of the last one (or beyond) is now marked "Whole day?" on its
  own: the form ticks the box and says why, and a request created any other way without saying
  gets the same treatment. It is a proposal: the employee can untick it when they do come in
  that day (a lesson moved to another time, which the guard duty board can arrange), and the
  Head can correct it either way.
- The comparison uses what the employee was really expected to work that day (public holidays
  and already approved absences left out); a day with no lessons is never turned into a whole
  day.
- The teachers' and Heads of Studies' manuals now state the rule explicitly, and why `Health`
  and `Invasive medical test` requests open as a whole day.

# Internal changes:

## Tests no longer fail when the suite runs on a public holiday:
- `TestEmployeeAutocheckout` and the automatic check-in tests of `TestAttendanceSessionHeader`
  give their teacher lessons on the real "today"; on a public holiday nothing is expected of
  anybody, so 13 of them failed (found on 2026-10-12, a holiday in the database). A new
  `make_working_day()` helper in `tests/common.py` removes the holidays around the fixture day
  inside the test's own transaction.

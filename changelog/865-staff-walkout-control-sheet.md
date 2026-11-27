# What's new

## Walkout control sheet to print (xlsx):

- The staff walkouts dialog (Absences > Reporting > Staff walkouts) has a new **Control sheet (xlsx)** button and an optional **Area** (VET, ESO / BTX; empty = every teaching area). It downloads a spreadsheet with two sheets per area, to print before or during a walkout day and note down who comes.
- **By period**: every teacher once, in the first period of their schedule that day, grouped by period, with department, contract type, activity, group, classroom code and name, expected students, and blank columns for students present, present, arrival time and remarks. Teachers with an absence request covering that period (approved or awaiting approval) are greyed and say which.
- **Grid**: every teacher by period, like the guard duty board, with the group (expected students and classroom code) or the duty, and a box to tick.
- Expected students come from the class's roll-call list; without one (ESO/BTX, no enrollment per subject) from its main groups' students; empty for split, optional or reinforcement groups, whose students EMS does not record.
- The attendance columns come filled in with what EMS knows when the sheet is downloaded: each teacher's attendance (present once checked in, on walkout when their first period has started without a check-in, absence when a request covers it) and first check-in time, and the students present in each class's roll call taken that day (empty if not taken yet).
- Beside each period, a small table of formulas headed **Cumulative figures** gives the figures so far per contract type (on walkout, present, absent), counting that period and every earlier one; the attendance cells offer those values as a list, so the figures follow whatever is filled in by hand.
- With every area (no area chosen), a first **Total** sheet gives the overall view of the walkout: every period of every area, each with only the cumulative figures of the whole teaching staff, as formulas over the areas' sheets.
- Any day can be chosen, also a coming one. Built on the fly from the same schedule reading as the guard duty board and the walkout report (0.18 s for the data and 0.08 s for the file on the dev database's 119 teachers).

# Changes

## Staff walkouts report for Heads of Studies too:

- Each line of the walkout report carries the employee's area (VET, ESO / BTX, ASP), so the figures can be filtered or grouped by area afterwards, in the pivot and the list.
- The walkout report and its control sheet follow the same access as the other reports under Absences > Reporting (by Employee, by Type, Monthly totals): the Time Off officers, that is the Heads of Studies, their Deputies and the Director. It used to be the Director's only.

# Internal changes

## Shared helpers for the walkout report:

- `ems.absence_pending._ems_scheduled_slots()` returns a day's schedule slots (the guard duty board's reading); `_ems_scheduled_periods()` is built on it. The public-holiday check of the walkout report is shared with the control sheet.

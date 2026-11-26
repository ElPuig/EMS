# What's new

## Walkout control sheet to print (xlsx):

- The staff walkouts dialog (Absences > Reporting > Staff walkouts) has a new **Control sheet (xlsx)** button and an optional **Area** (VET, ESO / BTX; empty = every teaching area). It downloads a spreadsheet with two sheets per area, to print before or during a walkout day and note down who comes.
- **By period**: every teacher once, in the first period of their schedule that day, grouped by period, with department, contract type, activity, group, classroom code and name, expected students, and blank columns for students present, present, arrival time and remarks. Teachers with an absence request covering that period (approved or awaiting approval) are greyed and say which.
- **Grid**: every teacher by period, like the guard duty board, with the group (expected students and classroom code) or the duty, and a box to tick.
- Expected students come from the class's roll-call list; without one (ESO/BTX, no enrollment per subject) from its main groups' students; empty for split, optional or reinforcement groups, whose students EMS does not record.
- Any day can be chosen, also a coming one. Built on the fly from the same schedule reading as the guard duty board and the walkout report (0.18 s for the data and 0.08 s for the file on the dev database's 119 teachers).

# Changes

## Staff walkouts report for the whole management team:

- New group **Management team > Member** (Settings > Users > Access Rights, EMS section), assigned by hand to whoever sits on the management team. The walkout report and its control sheet are now for this group instead of the Director only; the Director always belongs to it (implied), so nobody loses access on upgrade.
- A member who is not a Time Off officer (e.g. the Secretary) sees Absences > Reporting with only Staff walkouts in it: the other reports there (by Employee, by Type, Monthly totals) are now explicitly for Time Off officers, who already were the only ones to see them.

# Internal changes

## Shared helpers for the walkout report:

- `ems.absence_pending._ems_scheduled_slots()` returns a day's schedule slots (the guard duty board's reading); `_ems_scheduled_periods()` is built on it. The public-holiday check of the walkout report is shared with the control sheet.

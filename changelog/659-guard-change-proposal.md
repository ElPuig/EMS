# What's new

## Guard duty board: change a timetable change already told to the families, with one correction:
- A notice already sent (later entry, earlier leave, longer break, no classes) can now be changed
  until its time comes, from a **Change proposal** button on the lines it struck out (only for
  whoever organises the absence). The dialog offers another change the absences allow, the usual
  timetable, or an internal arrangement of the group's day planned as if nothing had been told
  (swaps, moved lessons). Whatever is chosen goes out as one correction to the group's students
  and families, never a cancellation plus a new notice.
- `_get_absence_change_states()` gives a communicated, still-allowed side `change_options`; rows
  carry `change_side`; new RPC `ems.course.get_change_proposal_options()`; the
  `ems_reopen_side` context key (`_reopened_side()`) makes the planner and
  `_get_needed_absence_block()` treat that side as untold; `board_apply_plan()` takes `reopen`.

## Guard duty board: corrections in a red box, inside every proposal of their groups:
- A group whose families were told something that no longer matches the absences goes in a new
  red box, **Corrections to absences already organised**, above the orange proposals box. Every
  proposal of its groups includes the correction as a step (step kind `correction`, built in
  `_arrangement_plan_records()` per group before grouping), and so does its **Only tell the
  families**. Each group gets one email: a plan's notice and its correction no longer
  go out separately, and unchecking the rest sends the correction alone.
- `board_apply_plan()` accepts `correction` steps and creates one notice per group, a correction
  whenever one of its changes is on a side already told.

# Changes

## Guard duty board: "Only tell the families" is a list of steps:
- In both boxes, its timetable changes (and corrections) are now steps with a checkbox, applied
  together with **Apply the checked steps** like an arrangement plan, one notice per group, instead
  of one **Send notice** button per row. A notice that could not be sent shows **Open draft** on its
  step.

## Guard duty board: every line still to be covered answers the pointer:
- A teacher who is not on guard duty at that time now gets the hand pointer and the tooltip
  "You cannot cover this teacher: you are not on guard duty at this time" (also on click), instead
  of a line that does nothing.

# Fixes

## Guard duty board: a correction said "(now: False)":
- When the absences no longer allow any change, the correction's sentence said "(now: False)";
  it now says "(now: Usual timetable)".

# Internal changes

## Tests and documentation for #659:
- `TestAbsenceCoverage` (12 new tests), three new tours in `TestAbsenceCoverageTour` (change
  proposal dialog, corrections box, not on guard), two new manual screenshots
  (`TestDocsScreenshotsTeachers.test_capture_guard_duty_change_proposal`) and the board's earlier
  ones regenerated, teachers' guard duty manual (en/ca/es), developer doc and ca/es translations
  updated.
- Quality audit before closing (now a standing rule in CLAUDE.md, "Quality audit when closing"):
  the plan corrections moved into the plan builder (it also fixes a correction back to the usual
  timetable that contradicted a plan repeating what was told), one lookup helper for a change's
  state (`_find_change_state()`), one client method to send a change, redundant tests removed and
  the missing ones added. Measured on real data: board load 0.2-0.3 s, the change dialog's plans
  0.03 s.

# Related with
- Closes #659

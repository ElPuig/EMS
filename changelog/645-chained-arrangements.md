# What's new

## Chained internal arrangements on the guard duty board (#645):
- The board now proposes arrangements as plans of several steps, not just one moved lesson or one swap: a teacher brings a lesson into the gap the absence leaves, another teacher brings one of theirs into the gap that leaves, and so on, until what is left free reaches the start or the end of the day (or a break) and the families are told the group comes in later, leaves earlier or has a longer break. Up to four steps per plan, swaps included.
- Plans are ranked by what matters to the students: first the fewest lessons lost, then the fewest hours in the centre without class (with a guard or in a longer break), then the fewest guards, notices to the families, teachers moved, subject hours split in two and changes to teachers' entry/exit times. The best three are shown. On the real case that prompted it (two groups whose tutor was away at the start and near the end of the afternoon), the first proposal is exactly what the Head of Studies worked out by hand: two teachers bring their two hours forward, a third brings in the last lesson of the day, and both groups leave one lesson earlier, with no guard.
- A lesson shared by several groups can now be moved, when every one of those groups has the same gap: it is moved for all of them, with one notice per group.
- Each plan shows as "Proposal N:" with its steps listed below it, one per line with its checkbox on the left (and, under a step, the entry/exit times it changes). All steps are checked; the planner can uncheck some (all of it except the notice, for instance). A step that needs another one (a move into the gap another one leaves, a notice freeing the group from a lesson a move left free) is unchecked with it, and the server checks the combination again before applying it. Plans show in the proposals box and in the dialog of every row they solve.
- The late entry / early leave proposals and the arrangements are now one box, "Proposals for the absences", with one section per group (together with the groups sharing lessons with it): what is waiting (an arrangement waiting for its notice, a notice to correct), then the arrangement plans, the best first, and last "Only tell the families", the timetable change alone with its selector, as one more proposal.
- A lesson moved without telling the families is in effect at once, and the lesson it leaves free becomes one more row of the absences table ("Lesson moved to 15:00"), covered like any other: a guard, a manual arrangement or another plan. Whoever organises the absence organises it.

# Changes

## Arrangements on the guard duty board (#645):
- A moved lesson is no longer applied on its own with its notice: it is a step of a plan, and the notice is another step that can be left out. Swaps and manual arrangements work as before.
- Withdrawing a lesson moved for several groups withdraws it from all of them.

# Internal changes

## Arrangement planner (#645):
- New `ArrangementPlanner` (models/attendance/arrangement_planner.py), a query-free beam search over moves and swaps fed by `ems.course._arrangement_planner()`; plans cached per set of groups linked by shared lessons. `_get_arrangement_plans()` replaces the moved lessons of `_get_arrangement_options()`, which now only detects swaps; `_simulate_moved_lesson()` is gone. The arrangement context indexes the day's timetable by teacher, so the many "is this teacher free?" questions no longer filter the whole centre's timetable each time.
- New `ems.absence_cover.board_apply_plan(day, steps)`; `board_arrange()` only takes swaps and manual arrangements. Board rows carry `arrangement_plans` (instead of `arrangement_options`) and `moved`; the pending action type is `arrangement_plan` (instead of `arrangement_option`).
- Permission checks on a class freed by a moved lesson follow the chain back to the absent teacher (`_original_absent()`, `_check_cover_manager()`).
- Measured on a real centre's timetable: about 55 ms for the plans of two linked groups, about 0.3 s for both shifts of the whole board.

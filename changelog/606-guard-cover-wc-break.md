# What's new:

## WC and break guards can be covered by regular guards (guard duty board):
- New `ems.non_teaching_type.is_regular_guard` ("Regular guard", seeded only on `G`; shown on the non-teaching type form when "Is guard duty" is ticked and on its list), so which guard duties are regular is configurable instead of hardcoded (developer's decision, 2026-10-09).
- When the teacher of a guard duty that is not regular (WC, break...) is away, their duty becomes one more row of the board's Absences table, with the duty's name where a class shows its group. It is covered like a class (developer's decision): the absent teacher's chain of command sends a regular guard with a notification ("cover this guard duty"), a regular guard can take it themselves (#601), it is offered for release when no longer needed, and it counts in the per-guard cover counter (#600). The PDF prints it too.
- Only teachers on a regular guard duty are offered to cover anything: break guards are now excluded as well, not only WC guards (developer's decision); the "(WC)" tag on the board is unchanged.
- `ems.absence_cover` covers either a class (`group_id`, no longer required) or a guard duty (new `duty_id`), exactly one of the two (SQL constraint); `board_assign()`/`board_self_assign()` take an optional `duty_id`; new `ems.course._get_needed_duty_entry()` and `_board_duty_rows()`.
- Backend tests in TestAbsenceCoverage, new tour `ems_wc_guard_cover` logged in as the absent guard's Department Chief; ca/es translations; teacher and admin manuals (3 languages) and developer docs updated.

# Internal changes:

## Branch 606 starts from the ready-to-merge guard branches:
- Branch 606 merges #599, #600 and #601 (all touching the guard duty board) before its own work; the #600/#601 conflicts (board payload, developer doc, ca/es translations) were resolved keeping both sides.

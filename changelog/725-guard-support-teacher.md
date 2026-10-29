# What's new

## Send a guard teacher as support to a teacher in class (issue #725):

- On the guard duty board's absences table, whoever manages a teacher's absences in a group (the Department or Seminar Chief of the group's department or of the teacher, up the chain to the Head of Studies and the Director, and the administrator) can click a guard on duty in the guard column and send them to support a teacher who is in class: a dialog lists the classes of that period whose teacher is in and that the user manages, with a message.
- Only a free, regular guard of the user's own area can be sent (same rule as sending a guard to cover, issue #721), for the part of the class their guard duty overlaps; a past day is read-only.
- The guard and the teacher are both notified (Odoo inbox or email, in their language, with the message), and again when the support is removed from the same dialog.
- While supporting, the guard is struck out of the guard column ("With <group>: Support for <teacher>"), is no longer offered to cover absences or to take one themselves, and no internal arrangement moves them. The timetable view and the PDF show the support in the class cell, and it counts in the guard's "covered this course" number.
- On the absences table, every guard the user can do nothing with looks disabled, so the ones they can send stand out; a teacher on guard sees themselves enabled (they may take a class themselves) and their colleagues disabled. A guard covering a class keeps its cover colour.
- A support never resolves an absence: if the supported teacher is away afterwards, their class is still to cover.

# Internal changes

## Support stored as a kind of absence cover (issue #725):

- `ems.absence_cover.cover_type` gains `support` (`absent_employee_id` = the teacher supported); new `get_support_options()`/`board_support()`, release through the existing `board_release()`. Every place that matches covers to absences leaves supports out, and `_arrangement_busy()` counts them.
- `ems.course._is_absence_manager()` takes an optional per-load cache of the group side and the teacher side, used by the board (the old per-pair `setdefault` never actually cached); `_may_manage_absences()` is a one-query pre-check so plain teachers pay nothing for the new flags.
- The support is created through the same `_board_create_cover()` as a guard cover (subject and room from the teacher's own lesson).
- Tests: `TestGuardSupport` (9, "also managed by" included) and the `ems_guard_support` tour, as a Department Chief; the shared fixtures of `TestAbsenceCoverage` moved to `AbsenceCoverageCase` (with `_two_areas()`).

# What's new

## Custom schedule: one subject split across several groups (issue #534):
- A student's form has a new "Custom schedule" switch (Studies tab). With it on, any enrolled subject can be customized: its group's sessions become editable slots, and each slot can be removed or replaced by a session of another group of the same level, including a group of a different study (e.g. 2 h with SMX1C and 2 h with SMX1D, or recovering a subject with another study's group).
- New model `ems.enrollment.slot` (`models/contacts/enrollment_slot.py`). Only customized enrollments store slots; an enrollment without slots follows its group exactly as before. A slot is identified by its (group, weekday, start time, end time) key, not by a schedule line id, so it survives the sync pipeline archiving and cloning lines. Decided with the developer: slots are not generated for every enrollment, because those rows would be a second derived copy of the calendar to keep in sync on every schedule change.
- One rule (`ems.enrollment._ems_attends`) now decides which sessions an enrollment makes its student attend, and every consumer uses it: schedule-line rosters (`fill_students`, so every calendar resync honours the custom slots with no hook of its own), incremental roster changes on enrollment/slot create/write/unlink (`_ems_resync_student_lines`, replacing `_ems_sync_attendance_template_add/remove`) and the student's Schedule tab (and the tutor's attendance report that reuses it).
- When a teacher's schedule change moves a customized session to another time, the slot turns "Not taught" (red row), the student is not added to the new session, and a warning banner appears at the top of the student's form until someone reviews it. A room-only change keeps the slot valid.
- Grading is unchanged: the enrollment's group stays the grading group, so a student split across two groups is graded once.
- A main-group change keeps a customized subject's slots. Changing an enrollment's group now also moves the student between the two groups' attendance lists (it never did before).
- Same access as the enrollments themselves (secretary, Head of Studies and admin edit any student; a tutor edits their tutees; teachers read).
- Docs: `docs/en/developers/contacts/enrollment_slot.md` (new), `enrollment.md` updated.

# Fixes

## Consecutive roll-calls copied students from the previous period:
- Taking attendance for the second of two consecutive periods of the same template copied every student of the first period's roll-call, instead of only this period's own roster. It now copies the previous statuses only for the students of this period's roster, and gives the rest of the roster a fresh line. Found while implementing issue #534 (a student attending only one of the two hours), but it also affected any manual per-session roster change.

## Untranslated messages built inside comprehensions (working-schedules import, send wizards):
- `_()` finds the user's language by inspecting its caller's frame, which a generator expression (and, on Python 3.10, a list comprehension) runs in a frame of its own. The working-schedules import wizard's unresolved-conflict list ("A vs. B") was therefore always shown in English, on every Python version, and on Python 3.10 so were its room/schedule conflict lines, the missing-classroom warning, the summary's resolved group/teacher lines, and the "Not one of your students" note in the authorization and contact-data request send wizards.
- All ten calls now use `self.env._`, which takes the language from the environment. The two identical unresolved-conflict checks became one helper, `_raise_if_unresolved`. New test: `test_unresolved_conflict_list_is_translated_into_catalan`.

## Session names showed the weekday in English:
- An attendance session's name ("MP 0485: Programació (DAW1A) | Wednesday | 20:20 - 21:20") is stored once, in English, as the sort key, and was also what every user saw - in session pickers, roll-call headers and so on. The visible name is now computed in the reader's language ("Dimecres", "Miércoles"), and typing a weekday in that language in a session picker finds it. The stored English name is unchanged.
- Sessions are now listed by weekday number (Monday, Tuesday, ...) instead of alphabetically by their English name, which put Friday first. They are still grouped by subject and groups first, through a new stored field, `template_label`, filled automatically on upgrade.

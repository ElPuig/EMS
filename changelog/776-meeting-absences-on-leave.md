# What's new

## Meeting attendance marks people on leave by itself:

- An attendance session (NFC kiosk) justifies every pending person who has an absence or a leave request (approved or still requested, the same ones the guard duty board shows) overlapping the meeting, with the note "Has an absence" and never its type or reason. It is checked when people are loaded, when the meeting's date or time changes, and again when attendance opens and closes; a person whose absence is cancelled or refused before closing goes back to pending, whoever passes the tag anyway is present, and a state set by hand is never undone (`ems.meeting.presence._ems_sync_leaves`, new `on_leave` flag on the line).
- A minute with attendance written by hand moves those people from the attendees to the absentees and adds "<name>: Has an absence" to "About the absences", keeping the writer's own notes. It looks again when the minute is created, its time or attendees change and the meeting starts; the writer can put somebody back among the attendees and EMS leaves them there (`ems.minute._ems_sync_leaves`, new `on_leave_ids`).
- The note is written in the centre's language, since it ends up in the minute. Cost measured on the dev database: 122 people resolved in 6.6 ms cold (6 queries), 1.2 ms warm.

# Internal changes

## Shared absence test fixtures:

- `course_monday()` and `create_absence()` moved from the guard duty board tests to `tests/common.py`, reused by the meeting and minute tests.

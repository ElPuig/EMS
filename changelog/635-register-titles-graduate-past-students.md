# What's new

## Titles obtained registered in the academic history (import from Esfera and from the student form):

- New Planning and Grading → Grades → Import titles wizard (secretariat and admin): reads Esfera's list of title requests (CSV in Windows-1252 or UTF-8, or xlsx) and ticks "Title obtained" on each student's record of the chosen course (the previous course by default). Only the student identifier column (`Identificador de l'alumne/a` or `IDALU`) is required; `Curs`, `Estat de la sol·licitud` and the name columns are used when present (rows of another course left out; a student with only cancelled requests does not count). A preview lists each student's result before anything is applied. Both steps run behind the blocking overlay of the other imports; when the titles are registered the wizard stays open with a summary and downloads a CSV log with the result of every row.
- New "Register title" entry in the student form's Actions dropdown (secretariat and admin, students and withdrawals), to register one student's title, choosing the course of its history.
- Ticking the title anywhere (record form, the two wizards) carries over to the student: marked as graduated; a withdrawal becomes alumni (exit data kept); an active student with no group leaves the centre as a graduate of that course (pending enrollments cancelled, operational records cleared, portal revoked, Google suspension scheduled, contact archived as alumni); a student still in a group only gets the mark. The generator (transition/withdrawal) never triggers these effects.

# Internal changes

## Shared exit steps extracted from the withdrawal wizard:

- `res.partner._ems_cancel_pending_enrollments()` and `res.partner._ems_leave_centre(kind)` (clear operational records, convert, revoke portal, archive) now hold the steps of the withdrawal cascade, reused by the graduate exit of a registered title. No behaviour change for withdrawals.

## Manual screenshots for the title registration:

- `TestDocsScreenshotsTitles` (tests/test_docs_screenshots_academic_history.py) generates the three screenshots of the secretariat's titles manual (import preview, Actions entry, Register title wizard) from invented students.

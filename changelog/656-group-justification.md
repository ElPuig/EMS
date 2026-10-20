# What's new

## Justifying absences of several students or whole groups at once (issue #656):

- The "New" button of Student's Attendances > Justifications now opens a "Justify absences" assistant (`ems.attendance_justification_wizard`) with a "Mode" dropdown: "Students" (pick any number of students) or "Groups" (pick any number of main groups; every active student whose main group is one of them is justified).
- It still creates one `ems.attendance_justification` per student, so overlaps, previsions, record rules and reports keep working unchanged; an existing justification is still opened, edited and deleted from its own form (the list and form carry `create="0"`).
- Who may use it and what it offers is the same rule as before: an administrator, everything; anyone else, the groups they act as tutor of (the tutor and the chain above them through `tutor_scope_user_ids`) and their students. Re-checked server-side on "Justify".
- Students already holding a justification overlapping the period are skipped, not an error: the assistant warns about them before justifying, and the closing notification names them.
- Period, teacher, notes and attached files are copied to every justification; each one gets its own copy of the files (the filestore keeps the content once), so a file follows the access rights of the justification it belongs to.
- The pickers' domains are sent as text rather than id lists (for an administrator, the whole centre).

# Internal changes

## Shared session-line lookup for justifications:

- `EmsAttendanceJustification._justifiable_lines(students, start_date, end_date)` finds the session lines a period covers for many students in one search (grouped per student afterwards), used by both the form's onchange and the assistant, so justifying a group costs one query instead of one per student.
- The browser tour for creating a justification now runs as a tutor and justifies a whole group through the assistant; 6 new backend tests cover groups mode, skipped overlaps, tutor scope, permissions and per-justification attachment copies.
- "EMS" added to the LanguageTool ignore list (`scripts/i18n/lt_ignore.txt`).

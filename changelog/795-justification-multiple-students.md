# What's new

## One justification shared by several students (strikes, competitions):
- A justification now holds a list of students (`student_ids`) with a single comment and a single set of attached files, instead of one justification per student with the comment and a copy of every file each. Typical cases: a group on strike (only the students who signed the document), students from several groups at a competition.
- The list's "New" opens the justification form itself, which replaces the "Justify absences" assistant (issues #656 and #763, removed with its line model): "Add groups" adds every student of the groups picked (skipping, with a warning, those already justified over that period), "Add a line" picks single students, and the cross (×) removes one; each student is listed with their main group. Adding or removing a student later justifies or unjustifies only their lines.
- Creating, changing or deleting a justification requires acting as tutor of every one of its students (tutor, Head of Studies/Deputy or Director above them) or being an administrator; reading it only needs one of them. The comment and files are shared, so a tutor can't change a justification that also covers another tutor's students.
- The list shows the student's name or "N students" and the notes; it can be searched by student and by main group. The overlap check names the students in conflict, and the form warns about them before saving.
- Previsions: a session looks up each student's justification in a dict built once per session, instead of a nested loop over every justification of the period.
- Migration 18.0.0.47.0 merges every batch the assistant created (same teacher, period, notes and creation instant) into one justification with all its students, session lines, affected teachers and one copy of each file, which covers the 11/11 strike justifications. Justifications created one by one are left untouched.
- Tutors' manual (ca/es/en), developer docs, translations and tests (backend, migration and the creation tour, now through the form) updated.

# Internal changes

## Justification tours search their fixture instead of relying on the first page:
- The justification tours now filter the list by the fixture's student before opening it: with a real database the fixture can fall on the second page of the list.

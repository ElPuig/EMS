# What's new

## Tutors' manual for justifying absences:

- New tutor manual (Catalan, Spanish and English) explaining how to record an attendance justification for a tutee, attach the supporting document, and what happens to past and future absences within its period, with screenshots taken against invented data.

# Fixes

## Tutors blocked on justifications covering other teachers' sessions:

- A tutor got an "Access error" (no read access to Attendance session) when opening an attendance justification of their own student as soon as any other teacher took attendance within the justified period, so they could no longer check it or attach documents to it.
- Creating a justification for past absences only picked up the tutor's own sessions: the absences recorded by other teachers in that period were silently left unjustified.
- The justification now finds and lists every affected session regardless of who taught it (only for the student's tutor or an admin); tutors still cannot open, list or edit other teachers' sessions.

## "Notes" label shown in Spanish in the Catalan interface:

- The Catalan translation of the "Notes" label (used by the notes field/tab of many screens: justifications, sessions, groups, studies, subjects, employees...) read "Notas"; it now reads "Notes".

# Internal changes

## Manual screenshots test runnable again:

- The manual-screenshots test created its invented students without a Student ID (IDALU), mandatory for new students since #460, and its docstring pointed to a `./test.sh` invocation that runs 0 tests; both fixed, and it now also produces the tutors' justification screenshots.

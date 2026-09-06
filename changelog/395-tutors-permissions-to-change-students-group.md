# What's new

## Tutor can change a tutored student's main group:
- The group tutor can now edit their own tutorand's Main Group field directly from the student's form (Studies tab) - previously read-only for tutors, only admin/secretary could do it. The choice stays scoped to groups of the student's own study/level (the tutor still cannot change the study itself).
- Changing a student's main group (by a tutor, admin or secretary, or via a bulk student CSV re-import) now automatically moves that student's subject enrollments from the old group to the new one, including their attendance schedule roster and any open evaluation round lines. An enrollment already in a different group (e.g. a reinforcement group) is left untouched. The change is rejected with a clear error if a subject in the old group already has grades recorded for that student.
- Course transition / enrollment placement (which also moves a student to a new group, year over year) is deliberately unaffected - the outgoing year's enrollments stay as history and are not repointed.
- Before saving, a warning banner explains exactly what will happen: every subject enrolled through the current group will move to the new one, while subjects enrolled through a different group stay unchanged.

# Fixes

## Tutor field on the student form could reassign an entire group's tutor:
- The "Tutor" field shown on a student's own form mirrors the group's tutor for display purposes only, but was missing the guard that stops Odoo from wiring it up as editable - saving a change there would have silently reassigned the tutor for every student in that group, not just changed a label. It is now genuinely read-only.

## Teachers/tutors could not open any group's form:
- Viewing a group's enrollment breakdown (used internally to show its enrolled students grouped with their subjects) ran an internal data-refresh step under the viewing user's own permissions, which a plain teacher or tutor does not have for that specific step. Simply opening any group's form as a teacher/tutor failed with an access error; fixed by running that refresh as a system operation instead.

# Internal changes

## New user documentation:
- Added a tutor manual ("Changing a student's group") in the three languages, linked from the Tutors index, and short notes in the admin Groups manual and the secretary student-contacts manual pointing at the same new behavior.

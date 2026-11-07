# What's new

## Justify absences by group, leaving some students out:
- The "Justify absences" assistant lists the students about to be justified with a "Do not justify" checkbox per student, so a tutor can justify a whole group except the ones marked (e.g. in a strike, the students who didn't join it). Works in both modes (Students and Groups).
- The marks survive changing the period or the selection; the closing message names the students left out.
- The list is backed by a transient line model (`ems.attendance_justification_wizard_line`) that replaces the read-only `target_student_ids` preview; who gets justified is still resolved server-side, the lines can only take students out.
- Tutors' manual (ca/es/en) and its screenshot updated.

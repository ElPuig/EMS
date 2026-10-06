# Changes:

## Convalidations: the grade is asked for when convalidating each subject, and can be "without grade":
- The ✓ (Convalidate) button on each subject line now opens a dialog asking for the grade: 5 by
  default, or the one the previous studies hold (5 to 10), or "Without grade". Grade and
  "Without grade" stay editable on the line while the request is under review.
- "Without grade" is a new, explicit option on each line, distinct from a 5: the resolution PDF
  and the portal show "Convalidated" (Convalidat) instead of a number, both grade views show a
  plain "CV" (styled as passed), and the subject reaches the grades and the academic history with
  no grade (0, hidden in the history views), so it is left out of any average. A real 5 is now
  printed as 5 on the resolution; previously the default 5 was printed as "Convalidated". No
  migration: existing lines keep their grade.
- The "Convalidate pending subjects" action is removed: every subject must be checked, and
  graded, one by one.
- The teachers' and tutor's "Convalidated subject" notice says when it was convalidated without
  a grade.
- Head of Studies, teachers, tutors and families manuals updated (with a screenshot of the new
  dialog); developer doc updated.

# Changes:

## Convalidations: the grade is asked for when convalidating each subject, and can be "without grade":
- The ✓ (Convalidate) button on each subject line now opens a dialog with a "Mode" selection
  ("With grade", the default, or "Without grade"; a selection so more modes can be added later)
  and, with grade, the grade itself: 5 by default, or the one the previous studies hold (5 to
  10). Grade and "Without grade" stay editable on the line while the request is under review.
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
- The resolution email no longer shows "(grade 5)" for a subject convalidated without a grade.
- Head of Studies, teachers, tutors, families and admin manuals updated (with screenshots of the
  new dialogs); developer doc updated.

## Convalidations: refusing a subject asks for its reason, from a configurable catalog:
- The ✗ (Reject) button on each subject line now opens a dialog with a required "Reason",
  preselected with the most usual one, and optional "Details", like the documentation request
  dialog. Both are stated on the resolution PDF, the portal and the resolution email, and stay
  editable on the line while the request is under review.
- New catalog "Refusal reasons per subject" (translatable, drag-to-order, archivable), seeded
  with: contents not equivalent (preselected), shorter duration of the previous studies, previous
  studies not passed or accredited, subject not convalidable, other.
- Academic management > Configuration gets a "Convalidations" section holding this catalog and
  the documentation request reasons.
- The free-text refusal reason becomes the optional "Refusal details": lines refused before this
  change keep their text there and still count as explained.

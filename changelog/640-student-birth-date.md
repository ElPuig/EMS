# Changes:

## No student without a birth date (issue #640):
- Without a birth date EMS takes a student for a minor (portal managed by the family, minors' notices, Google minors' OU). An enrollment can no longer be confirmed for a student without one: `sale.order.action_confirm()` refuses it naming the students, which covers both the backend and the portal and is the step that turns an applicant (or a returning ex-student) into a student.
- Portal: when the student has no birth date, the enrollment confirmation asks for it as a required field (only for confirming, not for sending comments). It must be a past date no more than 100 years ago; it is saved on the student before confirming, and an invalid or missing one is reported on the page.
- Student form: the birth date is required when registering a new student (like the IDALU). An existing student without it shows a warning at the top of the form (secretariat and administration) instead of blocking the form's buttons, and the new "Without birth date" filter of the student list shows them.
- The GEDAC import is unchanged: its export has no birth date column.
- Test fixtures that confirm enrollments now give their students a (minor) birth date; the two tours that register a student from the form fill it in.

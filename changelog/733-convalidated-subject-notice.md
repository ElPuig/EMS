# Changes

## Convalidated subjects: a notice for teachers and tutors instead of a task:
- Completing a convalidation used to give each teacher of the subject and the group's tutor a "Convalidated subject" to-do on the student, one per subject, with a deadline: it showed as overdue and stayed in the daily task digest although there was nothing to do.
- They now get a notice (message_notify on the student: Odoo's inbox or email, as each user's preference says), one per request, listing the subjects that concern them with each grade and the registration number. No deadline, no follower added.

# Internal changes

## Convalidation notice activity type removed:
- The pre-migrate of 18.0.0.43.0 deletes the open "Convalidated subject" activities (without marking them done, which would post a message on each student) so that Odoo can drop the activity type, gone from the data files. Tests, user manuals (teachers, tutors, secretariat) and translations updated.

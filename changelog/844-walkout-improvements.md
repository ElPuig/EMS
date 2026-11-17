# Changes:

## Student walkout: off the roll-call instead of justified (issue #844):
- Every student who joins a walkout is off the roll-calls of its day ("Not required to attend: student walkout", the #644 archived-line mechanism) from the moment joining closes with the group's support: neither an absence nor a presence. Roll-calls taken later start that way (`res.partner._ems_not_expected_reasons` override, `models/contacts/student_walkout_attendance.py`); lines already taken are updated on closing, and a joining extended after closing syncs them again.
- Nothing is justified any more: the Head of Studies' "Validate and justify" is now "Validate" (`action_validate`, state `justified` renamed `validated`, task "Validate the student walkout"). Not validating it, or undoing the validation, turns those classes into regular absences (without emailing families about past days).
- The family's ratification of a minor is now informative only (it says the family is aware and agrees; nobody can revoke the decision). What it changes: the family of a minor who joins without it (pending, refused, no portal) gets the usual attendance notice of each class of that day, with a dedicated, purely informative text ("collective decision not to attend class", "it is not an absence nor a sanction"); the roll-call label tells the teacher. A ratification marked by hand later withdraws a pending notice.
- Removing a student from the roll-call again after putting them back by mistake recovers the reason that still applies (walkout, expected withdrawal or convalidation) and its notice; the roll-call reloads the line to show it.
- Texts for students and families (portal, emails, manuals) rewritten: a collective decision not to attend class that nobody can revoke, the classes of that day do not count as absences, and, for families, once ratified there is nothing else to do.

## Student walkout portal: answers confirmed in a pop-up (issue #844):
- After voting, saying whether one joins, extending the joining or ratifying, the page pops up what was saved and what comes next (`saved=<vote|join|extend|ratified|refused>`), and the joining form and the family's buttons fold under the answer with a "Change my answer" button while joining lasts.

# Internal changes:

## Student walkout migration (issue #844):
- `migrations/18.0.0.50.0/pre-migrate.py` renames the state `justified` to `validated` (also as `rejected_from_state`) and the task's xmlid; `post-migrate.py` deletes the justifications validated walkouts had created, drops `ems_student_walkout.justification_id` and takes the classes of the students who joined closed or validated walkouts off the roll-call, without notifying families.

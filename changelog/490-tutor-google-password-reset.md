# Changes

## Tutors can reset their students' Google password:
- The **Reset Google password** button on a student's form, so far limited to the academic
  admin and the TAC team, is now also offered to the student's own tutor, who already hands
  that student their credentials and no longer has to route a forgotten password through TAC.
- The right is resolved per record, not per role: `action_reset_google_password()` accepts the
  acting user when `ems.base.user_acts_as_tutor(partner.tutor_id)` is true, so the escalation
  comes from `hr.employee.tutor_scope_user_ids` (issue #483) - the tutor, every chief above
  them along `parent_id` holding `ems.group_department_chief` (Department/Seminar Chief and
  Head of Studies/Deputy, which imply it) and the Director of their company. A chief of a
  different branch gets nothing; a student whose group has no tutor stays with academic admin
  and TAC only.
- New non-stored computed field `res.partner.can_reset_google_password` (`compute_sudo`,
  `depends_context('uid')`) drives the button's own `invisible`: `rule_contact_teacher` lets any
  teacher read every student, so the button's `groups=` alone would have offered it on students
  the user cannot actually reset. The method re-checks the same field server-side, since a view
  attribute only hides.
- No new group, no new record rule and no ACL change: every write in the reset flow (cancelling
  the previous credentials documents, creating the new one, the chatter note, the welcome email)
  already went through `sudo()`, and the service-account JSON is read with `env.company.sudo()`.

# Internal changes

## Test and documentation coverage for the tutor-scoped reset:
- `TestStudentGooglePasswordReset` now builds a tutored group plus a full Head of Studies branch:
  the student's own tutor, the chiefs above them and the Director can reset, while a tutor of
  another group, an unrelated Department Chief, an unrelated Head of Studies, a plain teacher and
  the secretary cannot, and `can_reset_google_password` is asserted per user.
- New browser tour `ems_student_google_password_reset_tutor`, driven by a tutor (the
  least-privileged role now allowed to reset), which also asserts the tutor is offered none of the
  account-lifecycle buttons and reads the fresh credentials from the Documentation tab.
- Developer documentation, the tutors' trilingual manual (with a new screenshot of the header as
  the tutor sees it, captured through `test_docs_screenshots.py`), the Head of Studies index and
  the administrator manual updated, plus the Catalan and Spanish translations of the new field and
  the reworded permission error.

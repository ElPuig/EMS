# Fixes

## Batch actions on students: a tutor only reaches their own students (issue #550):

- "Send authorizations" and "Request contact data" opened from the students list used to preload
  every selected student, listing someone else's as "Not one of your students" in the preview.
  Now only the students the sender acts on (`ems.student.scope.mixin._scope_acts_on_student`:
  staff who see every student, or the tutor and the chiefs above them) are preloaded, so a tutor
  selecting the whole list starts from their own students only. Fixed once in the shared
  `_scope_students_from_context()`.
- "Request contact data" opened from the groups list does the same with the selected groups:
  only the sender's own groups (`_scope_allowed_groups()`) are preloaded.
- The student picker of both assistants now offers a tutor only their own students: a new
  `student_domain` default on the mixin (same pattern as `ems.em_grading_wizard.group_domain`),
  used as the view's `domain=`. The "Not one of your students" preview note became unreachable
  and was removed (code, tests, translations); `_resolve_students()` still filters server-side.
- "Portal access" already filtered to the tutor's own students; "Download Google credentials" is
  restricted by record rules.
- Tests: preloading from the students and groups lists, the picker's domain for a tutor and for
  staff, and the tutor send tour now checks the picker offers only the tutor's own student.
- Tutor manuals (authorizations, contact data requests) updated in the three languages.

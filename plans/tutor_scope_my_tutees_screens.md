# "My tutees" screens: open them to the chain of command, with a default "only mine" filter

**Status: not started (written 2026-09-24), decision already taken by the developer.** Found
during the role-permission audit that followed issue #500. Related to
`plans/permission_hierarchy_escalation.md` (the broader audit of flat, role-based rules).

## Problem

Issue #483 made tutor-scoped rights escalate along the real chain of command:
`hr.employee.tutor_scope_user_ids` / `ems.base.user_acts_as_tutor(tutor)` (the tutor, every chief
above them through `parent_id`, and the Director). CLAUDE.md requires every tutor-scoped rule or
check to use them, never `tutor_id.user_id`. Four "my tutees" screens still filter on
`tutor_id.user_id`, so a chief never sees their tutors' data there:

| Screen | Where |
|---|---|
| Tutor grade matrix | `static/src/js/backend/grade_tutor_matrix.js` (`group_id.tutor_id.user_id`) |
| Authorizations list for tutors | `models/enrollment/authorization.py` (action domain `partner_id.tutor_id.user_id`) |
| Authorization send wizard | `models/enrollment/authorization_send_wizard.py` (groups filtered on `tutor_id.user_id`) |
| Tutor's enrollment list | `views/academic_management/enrollment/list_tutor.xml` (server action domain `tutor_id.user_id`) |

(`models/coexistence/strike.py` also reads `tutor_id.user_id`, only for the notification's
language - not a scope check, leave it.)

## Decision (developer, 2026-09-24)

A chief must see everything their employees see, **with a default filter showing only their own**
- the same pattern already used elsewhere (e.g. the Plannings list's "Show only mine",
`search_default_only_mine`, and the attendance sessions' own filter).

## Proposed fix

1. Replace each hard domain on `tutor_id.user_id` with the tutor scope (the tutor's
   `tutor_scope_user_ids` containing the user), so the chain of command sees their tutors' data.
2. Add a "Show only mine" filter (the user is the direct tutor) to each list/search view, enabled
   by default through the action's `search_default_*` context; for the grade matrix (an OWL
   component, not a search view), an equivalent toggle defaulting to "mine".
3. The send wizard lists every group in scope, preselecting the user's own.
4. Tests as tutor, department chief and head of studies with the cross-ownership fixture from
   `plans/role_permission_test_coverage.md`: the chief sees the tutor's data once the filter is
   removed, and only their own by default.

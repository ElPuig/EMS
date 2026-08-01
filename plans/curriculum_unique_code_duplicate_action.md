Status: not started - found while resolving a merge conflict (2026-08-01), not yet fixed.

# Problem

Six `curriculum` models have a unique `code` `_sql_constraints` entry but no `copy()` override:

- `models/curriculum/study.py` (`unique_code`)
- `models/curriculum/subject.py` (`unique_code`)
- `models/curriculum/level.py`
- `models/curriculum/content.py`
- `models/curriculum/criteria.py`
- `models/curriculum/outcome.py`

None of their form/list views set `duplicate="false"`, so Odoo's standard "Duplicate" action
(Action menu on the form, or the list's context menu) is exposed for all of them - and clicking
it raises a raw `psycopg2.errors.UniqueViolation` (`duplicate key value violates unique
constraint "..._unique_code"`) instead of either working correctly or failing with a clear
message, since `copy()`'s default behavior copies `code` verbatim.

# How this was found

Not found by deliberately auditing these models - surfaced while merging in
`353-add-course-transition-wizard-setup-next-course` (Juan's branch): his new
`test_transition_state_is_not_copied` (`tests/test_course_transition.py`) calls
`self.study.copy()` (to check `transition_state` resets, unrelated to `code`) and hit this exact
constraint, because `ems.study.unique_code` was added on this branch after Juan's branch had
already diverged - the two changes never collided until the merge. Fixed *for that one test* by
passing an explicit `code` override in the `copy()` call (not a model fix) - see the git history
of `tests/test_course_transition.py` around that date for the exact change.

# Not yet done

Decide and implement, for all six models above, either:
- a `copy()` override that generates a genuinely unique `code` (e.g. appending a counter/suffix,
  same idea as Odoo's own default `name` "(copy)" suffix behavior), so "Duplicate" actually works,
  or
- explicitly disabling duplication (`duplicate="false"` on the relevant views, matching the
  pattern already used by `ems.attendance_session.copy()` which raises a friendly `UserError`
  instead) if duplicating one of these doesn't actually make sense for the model in question.

Worth checking, per model, whether an admin ever has a real reason to duplicate one (a new study
that's mostly the same as an existing one might be a real use case; duplicating a `criteria`/
`outcome` row is less obviously useful) rather than applying the same fix uniformly to all six.

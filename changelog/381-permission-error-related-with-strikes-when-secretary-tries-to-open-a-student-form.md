# Fixes:
## Secretary AccessError opening a student form (strike stat button):
`ems.group_secretary` had no `ir.model.access.csv` row at all for `ems.strike`. The student form's
"Strikes" stat button (`views/community/contact/form.xml`) has no `groups=` restriction, so
`res.partner.strike_count` (computed from `strike_ids`, a One2many to `ems.strike`) is always
fetched when the form loads, regardless of the button's `invisible` condition. With zero access
rows for the group, this raised an `AccessError` for every secretary opening any student's form,
even one with no strikes.

Added `ems.access_ems_strike_secretary` (read-only) to `security/ir.model.access.csv`, mirroring
`group_coexistence`'s read-only access. No matching `ir.rule` exists for `group_secretary` on
`ems.strike`, so (like `group_coexistence`) secretaries can read all strikes, unrestricted by
student/teacher scope - consistent with their existing broad read/write access on `res.partner`
and other student-record models. Added regression tests in `tests/test_strike.py` covering both
that a secretary can now open a student form without error and see existing strikes, and that
write/create still correctly raise `AccessError` for that group.

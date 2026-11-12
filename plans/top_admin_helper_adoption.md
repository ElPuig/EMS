# Use `ems.base.get_user_is_top_admin()` everywhere

**Status (2026-11-11): current, not started.** Found while closing issue #800.

`ems.base.get_user_is_top_admin()` (added in #800, `models/shared/base.py`) answers "is this user
the administrator at the top of the permission pyramid?": `env.su`, `base.group_system` or
`ems.group_academic_admin` (CLAUDE.md, "The administrator is always at the top of the permission
pyramid"). The same condition is still written by hand, with small variations (some forget
`env.su`, some forget one of the two groups), in at least:

- `models/erasmus/claim.py` (~152)
- `models/attendance/attendance_session.py` (~829)
- `models/employees/absence.py` (~1608)
- `models/employees/absence_pending.py` (~131)
- `models/attendance/guard_duty_board.py` (~524, cached per request)
- `models/settings/company.py` (~506)
- `models/contacts/withdrawal_expected.py` (~43)
- `models/contacts/ex_officio_withdrawal.py` (~970)

`grep -rn "has_group('base.group_system')" models` finds them.

## Plan

1. For each site, check whether the variation is deliberate (e.g. a check that must not include
   the academic administrator) before replacing it; ask when unclear.
2. Replace the rest with `self.get_user_is_top_admin()` (or keep the per-request cache of the guard
   duty board, filled from it).
3. Run each touched model's test classes; no behaviour change is expected except where a site
   forgot one of the two groups, which becomes a fix worth its own test.

Also worth checking at the same time: `get_user_is_admin()` itself only means the academic
administrator; its callers that really mean "top administrator" should move to the new helper.

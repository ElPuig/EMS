# Role-tour coverage: retrofit backlog for existing admin-only tours

**Status: current as of 2026-09-24.** Backlog, not started - ongoing, opportunistic work, not a
dedicated sprint. This is Phase 3 of the role-based tour coverage proposal (issue #434 follow-up;
Phases 0-2 are done - shared role-user factory in `tests/common.py`, the Development-workflow
login rule in `CLAUDE.md`, and the 5 generic per-role smoke tours,
`tests/test_role_smoke_<role>_tour.py`).

## What this covers

Of the ~78 existing tours that log in as `admin` (or a role implying `hr.group_hr_user`/
`group_system`), some render screens whose real least-privileged role does **not** imply
`hr.group_hr_user` - `teacher`, `tutor`, `department_chief`, `orientation`, `coexistence`,
`secretary`, `quality`. Those tours currently can't catch the #434 failure class (a widget field
dependency, a menu `groups=`, or client/server self-filtering silently locking such a role out of
a screen its ACL/record rules otherwise allow) because they never actually run as one of those
roles. The 5 generic smoke tours (`CLAUDE.md`'s "Per-role smoke tours") already give broad,
shallow crawl-only coverage of this; this backlog is about giving the highest-risk existing
*feature* tours deeper, assertive coverage under the right role too - not blanket retrofitting
all 78.

## Bounded identification method (don't read all 78 files by hand)

1. Grep for the exact #434 shape - a view that splits a field/widget by
   `groups="hr.group_hr_user"` / `groups="!hr.group_hr_user"`:
   ```bash
   grep -rl 'groups="hr\.group_hr_user"\|groups="!hr\.group_hr_user"' views/
   ```
   Run 2026-09-11: only `views/community/employee/kanban.xml` (the #434 fix itself) and one
   comment-only mention in `views/community/employee/form.xml` (not an actual split) - no other
   *unfixed* instance of this precise pattern exists in the codebase today.
2. Since (1) found nothing new, widen to the same risk **domain** even without the exact XML
   marker - views touching `hr.holidays`/`hr.attendance`/presence data, which is where a future
   native-module change is most likely to introduce a similar dependency:
   ```bash
   grep -rl "hr_presence\|hr\.holidays\|current_leave_id\|hr_attendance" views/
   ```
   Run 2026-09-11, candidates beyond the already-fixed employee kanban/form:
   - `views/attendance/absence/leave.xml`
   - `views/attendance/attendance_correction/hr_attendance_form.xml`
   - `views/settings/hr_attendance_form.xml`
3. For each candidate view, find which tour(s) actually render it (trace the `<menuitem>`/action
   chain the same way `CLAUDE.md`'s view-folder-tracing rule already describes), confirm which
   tour(s) currently log in as admin, and whether the least-privileged real role for that screen
   is one of the 7 at-risk roles above.

## Checklist

Fill in as each candidate is actually traced and, if warranted, retrofitted (add a second
`start_tour`/test method logging in as the right role via `create_role_user`/
`create_role_employee`, or convert the existing login if admin was never actually required):

- [ ] `views/attendance/absence/leave.xml` - identify rendering tour(s), least-privileged role,
      retrofit if needed.
- [ ] `views/attendance/attendance_correction/hr_attendance_form.xml` - identify rendering
      tour(s), least-privileged role, retrofit if needed.
- [ ] `views/settings/hr_attendance_form.xml` - identify rendering tour(s); this one may
      legitimately be settings/admin-only, confirm before assuming it needs a change.

Added 2026-09-24 (role-permission audit after #500, see `plans/role_permission_test_coverage.md`):
at that date 72 of 103 tour files logged in as `admin` only. Most are configuration screens that
are genuinely admin-only, but these are daily screens of teaching roles and go first:

- [ ] `test_grade_session_tour.py`, `test_grade_matrix_tour.py`,
      `test_grade_session_state_wizard_tour.py` - teacher entering grades.
- [ ] `test_em_grading_wizard_tour.py` - tutor grading the work placement.
- [ ] `test_strike_tour.py` - any teacher putting a strike.
- [ ] `test_notice_tour.py` - teachers/heads sending notices.
- [ ] `test_attendance_correction_request_tour.py` - any employee requesting a correction.
- [ ] `test_attendance_issue_tour.py`, `test_attendance_template_tour.py` - teacher's attendance.
- [ ] `test_enrollment_proposal_tour.py`, `test_portal_access_wizard_tour.py`,
      `test_family_tour.py` - tutor screens.
- [ ] `test_year_record_tour.py` - teachers/tutors reading the academic history.

Work this in batches of ~8-12 tours at a time, opportunistically alongside other work that
already touches the same view/tour - not as a dedicated pass. Re-run the two greps above
periodically (or when a native Odoo module upgrade changes a widget), since new candidates can
appear over time the same way #434 did.

Once this backlog is fully worked through (or a future audit concludes no further retrofit is
warranted), delete this file - `git log` keeps the history.

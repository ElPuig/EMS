# Role-permission test coverage: close the gaps #500 slipped through

**Status: not started (written 2026-09-24).** Design plan from a role-permission audit run after
issue #500 (a tutor's access error in the by-student attendance report). If the per-role smoke
tours, `tests/common.py` role helpers or the listed screens change before this is picked up,
re-check the gaps below before acting on them.

## Origin

The #500 bug only showed up when a role **did something** (picked a student in a wizard) on
**someone else's data** (sessions taught by another teacher, behind a stricter `ir.rule` than the
session lines). No existing test combines both conditions.

The 2026-09-24 audit checked the current code empirically on a production-derived dev database,
as real users of 8 roles, in rolled-back transactions: 0 access errors rendering the 13 EMS PDFs,
opening real records in every menu-reachable view (1437 reads), running the daily teacher flows
(108 users) and the org chart. So nothing is broken today; this plan is about making CI catch the
next one without needing real data.

## Gaps found

1. **The role-smoke crawler (`static/tests/tours/role_smoke_common.js`) never:**
   - opens a wizard (`action.target === "new"` is skipped) - the #500 screen was one;
   - opens an existing record (form views open blank, `action.limit = 1`);
   - clicks a button, prints a report or calls a widget RPC method.
2. **No smoke tour for `tutor` or `head_of_studies`.** They were left out as having the same
   menu reach as other roles, but their permissions depend on *whose* data it is (tutees, chain
   of command) - where #448, #480, #483, #500 and the 2026-09-24 planning-outcome unlink gap all
   landed.
3. **Fixtures never cross an ownership boundary**: the role user owns everything it touches.
4. **10 of 13 PDFs are only rendered as superuser in tests** (`self.env[...]._render_qweb_pdf`,
   bypassing every rule) or never: `report_group_schedule`, `report_space_schedule`,
   `report_working_schedule`, `report_student_schedule`, `report_guard_duty_board`,
   `attendance_report_session`, `report_authorization_certificate`, `report_google_credentials`,
   `report_google_credentials_employee`, `report_enrollment`. Only the three attendance report
   wizard PDFs are rendered as a role (since #500). A single render of `report_enrollment` would
   have caught its "incomplete format" crash (fixed 2026-09-24).

## Proposed scope

1. **Shared cross-ownership fixture** in `tests/common.py`: two teachers teaching different
   subjects to the same group, a tutor of that group who teaches the student nothing, a
   department chief and a head of studies above the tutor through `parent_id`, attendance
   sessions by both teachers, open grade sessions, an enrollment with a discounted line.
2. **Reports as every role** (`TransactionCase`): for each EMS `ir.actions.report` and each
   role that can reach it, render it `with_user(role)` on the fixture's records, including one
   the role reaches only through tutor/chain scope. Iterate over the reports found via
   `ir.model.data` so a new report is covered automatically.
3. **Daily flows as each teaching role** (`TransactionCase`): session list, start own and guard
   session, write a line, create a strike, guard board data, tutor matrix reads - the same calls
   the widgets make (`attendance_session_view.js`, `guard_duty_board.js`,
   `grade_tutor_matrix.js`).
4. **Crawler:** add `tutor` and `head_of_studies` smoke tours; after opening each list, also open
   its first record in the form view; open wizards reachable from the menu with their default
   values (skip-list for the ones that need `active_id`).
5. Keep the per-screen feature-tour retrofit in `plans/role_tour_coverage_retrofit.md`.

## Risks / to decide

- The crawler runs against whatever data the database has: on CI's clean install there are few
  records, which is why points 1-3 are TransactionCase tests over an explicit fixture rather
  than crawler changes alone.
- Wizards opened with no context may raise deliberate `UserError`s (as `ems.enrollment` and
  `ems.attendance_justification` already do) - those go on the crawler's skip-list, documented.

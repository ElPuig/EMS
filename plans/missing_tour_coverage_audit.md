# Full UI-coverage re-audit (v2) — every screen must render without crashing

**Status: current as of 2026-07-31. Supersedes the "audit complete" declarations from earlier
today in this same file's history (see git log) — those were wrong, twice, and this file was
rewritten from scratch after a proper mechanical re-audit rather than another manual
enumeration pass.**

## Why this got redone

Earlier today this plan was declared "complete" after a large batch of tours were added, then
had to be reopened twice in the same day because the developer's own spot-checks found real
gaps the "complete" declaration had missed (the daily roll-call screen's core action, then the
attendance-template creation flow, then the attendance-justification creation flow). The
developer then asked directly: **has anyone actually verified every EMS screen renders without
crashing, or are we still trusting an incomplete manual enumeration?** Fair question — the
previous passes were done by reading `views/` and comparing against `static/tests/tours/`
manually/from memory, which is exactly the kind of exhaustive-enumeration task a human (or an
LLM working from partial context) reliably under-counts.

This pass instead did a **mechanical, two-sided enumeration**:
1. Every UI-reachable screen: `<menuitem>` actions, `ir.actions.act_window`/`ir.actions.client`
   records, buttons that open another screen (`type="object"`/`type="action"`), cog-menu/list
   context-menu wizards (including 5 that are pure-JS with no `binding_model_id` in XML at
   all — these would be invisible to a grep for that attribute), and every embedded
   one2many/many2many sub-view rendered inline inside another model's form.
2. Every existing tour's actual reach: which action it opens, whether it ever gets past the
   list into a form, which notebook tabs it clicks, which embedded sub-views/dialogs it
   touches.

Then cross-referenced by hand (not delegated) to find genuine gaps. Both enumeration passes and
the cross-reference were independently spot-checked against the actual XML/JS (not trusted at
face value) — see "Verified findings" below.

**Numbers:** 64 `ir.actions.act_window` + 2 `ir.actions.client` + 7 cog-menu/list-context-menu
wizards = ~73 distinct top-level screens. 63 tours exist across 53 files (zero orphaned, zero
dangling `start_tour` calls — the JS/Python pairing itself is solid). The gap is entirely in
**which of the 73 screens (and which notebook tabs/embedded sub-views within the covered ones)
a tour actually opens.**

## Two real navigation bugs found along the way (unrelated to tour coverage, fix regardless)

1. **`menu_work_locations` id collision — "Work locations" menu entry is currently invisible.**
   `views/community/work_location/menu.xml` and `views/community/working_schedules/menu.xml`
   both declare `<menuitem id="menu_work_locations">` with different names/actions/parents.
   Manifest load order (`work_location/menu.xml` before `working_schedules/menu.xml`) means the
   second silently overwrites the first — "Work locations" (`hr.work.location`,
   `action_work_location_tree`) has had **no menu entry at all** since whenever these two files
   started colliding, even though the action/views themselves work fine (confirmed:
   `work_location_tour.js` reaches it directly by URL, bypassing the broken menu). An admin
   clicking through "Community > Configuration > Human resources" today only ever sees
   "Working schedules" twice in effect — "Work locations" doesn't exist to them. Fix: rename one
   of the two `<menuitem id="...">`.
2. **`action_student_form` xmlid collision — dormant but a landmine.** Declared twice with the
   identical id `ems.action_student_form`: once properly (in `contact/menu.xml`, domain +
   search view), once with a hardcoded `res_id="57"` and no domain (in `group/form.xml`, load
   order makes this one win). Not currently referenced by any button/menu, so no user hits it
   today — but the first person who does (or the first environment where partner id 57 isn't a
   real student) gets a broken screen. Fix: rename the accidental duplicate in `group/form.xml`
   or remove it if it's genuinely dead.

## Verified gaps, grouped by risk tier

### Tier 1 — whole screens with ZERO tour coverage (the exact failure mode the developer is worried about)

| # | Screen | Action / model | Notes |
|---|---|---|---|
| 1 | **Evaluation for tutors** | `action_grade_tutor_matrix` (`ir.actions.client`, bespoke OWL widget) | Same *category* of risk as the daily roll-call screen (`ems_attendance_session_view`) that turned out to be the actual gap earlier today — a custom client action, not a standard form, with genuinely zero tour driving it. Teacher-facing. Highest priority. |
| 2 | **Enrollment proposal** | `ems.action_student_group_enrollment` (server action) → `act_window_student_group_enrollment` (res.partner) | Launches `ems.graduation_wizard` via a header button — that wizard form (with its embedded `line_ids`) is also untested. |
| 3 | **Preinscription** | `action_ems_applicants` (res.partner, applicant domain) | Also launches `ems.enrollment_proposal_wizard` (own form + embedded `student_ids`, zero coverage) and its cog-menu import-GEDAC button (the wizard it opens IS tested, but only via direct URL — the cog-menu click path itself is unverified). Also the only path to `res.partner`'s "Applicant data" notebook tab. |
| 4 | **Students without destination** | `action_students_no_destination` (res.partner) | Also launches `ems.enrollment_proposal_wizard` (see #3). |
| 5 | **Academic history** | `action_year_record_list` (`ems.student.year_record`) | Also the only path to `res.partner`'s "Academic history" tab (`year_record_ids`) and to the nested `ems.student.year_record.subject` → `outcome_record_ids` hierarchy — a full 3-level model chain with zero rendering evidence. |
| 6 | **Plannings** | `action_planning_tree` (`ems.planning`) | Ponderations config; has `TransactionCase` coverage (`test_planning.py`) but no tour — embedded `planning_outcome_ids` also unrendered. |
| 7 | **Import grades** | `action_grade_import_wizard` | Wizard form + `_build_result_html` (the shared-helper HTML list) never rendered in a browser. |
| 8 | **Work placement evaluation (EM)** | `action_em_grading_wizard` | Own form + embedded `line_ids`/`student_line_ids`. |
| 9 | **Minutes** | `action_minute_tree` (`ems.minute`) | The model that replaced the deleted `ems.record` — never got a tour. |
| 10 | **Providers** | `action_provider_kanban` (res.partner) | Distinct action/domain from the well-tested Students/Families kanbans. |
| 11 | **Enrollments** (config) | `action_enrollment_tree` (`ems.enrollment`, Community > Configuration > Students) | Distinct from the well-tested `action_ems_enrollments` (`sale.order`) — different model, same-sounding name, easy to conflate (this is likely *why* it got missed before). |
| 12 | **Surveys → Recipients tab** | `ems.limesurvey_header`'s `limesurvey_recipient_ids` tab, plus `ems.limesurvey_recipient`'s own 3 views (main form, add-student popup, error popup) | `limesurvey_block_tour.js` only ever opens the "Blocks" tab on the same header form. |
| 13 | **Employee Attendances (native) form's EMS additions** | `hr.attendance` xpath — adds `action_view_corrections`/`%(ems.action_attendance_correction_new)d` buttons | No EMS tour ever opens the native check-in/check-out form at all, so these EMS-injected buttons (and the "new correction request" flow they lead to) have zero coverage. |

### Tier 2 — secondary/alternate actions on an already-covered model (lower risk: the view *architecture* is proven by the primary action, only the specific action+domain is new)

- **ASP** (`action_asp_kanban`, hr.employee) — Teachers kanban is heavily tested; ASP domain isn't.
- **ASP roles** (`action_asp_role_tree`, ems.role) — same relationship to the well-tested Teachers-roles action.

### Tier 3 — notebook tabs / embedded sub-views on an otherwise-covered screen, never clicked

Verified directly against each form's XML (not assumed):

- `ems.level` form → **"Studies"** tab (`study_ids`) — `level_tour.js` never opens a single tab.
- `ems.study` form → **"Subjects"** and **"Attached files"** tabs — `study_tour.js` never opens a tab either.
- `ems.authorization.template` form → **"Fields"** tab (`field_ids`) — `authorization_template_tour.js` only touches `name`/`legal_text`.
- `ems.group` form → the **reinforcement-type "Students"** page (a second, separate `<page>` distinct from the main-type one already covered) — `group_tour.js` creates a reinforcement group but never opens its Students tab.
- `res.partner` form → **"Former student"** tab — no tour opens an already-withdrawn student's own form afterward.
- `ems.attendance_template` form → **"Students"** tab (`student_ids`, separate from the already-covered "Sessions" tab).

(`res.partner`'s "Studies"/"Secretary" tabs, despite hosting `enrollment_ids`/`ems_authorization_ids`,
ARE already covered — `contact_tour.js` clicks both. Verified directly to avoid a false positive.)

### Tier 4 — cog-menu buttons that exist but are never actually *clicked* (the wizard they open IS tested, just via direct URL, not via the real click path)

`import-gedac-cog-menu`, `import-student-cog-menu`, `update-student-cog-menu` — lower risk since
the target screen's own render is proven; only the button's registration/click-wiring on the
list toolbar is unverified.

### Tier 5 — isolated popups/buttons (matches the "un botón concreto, lo asumo" tolerance the developer stated — listed for completeness, not proposed for active work)

`open_exception_popup` (attendance_issue/notice forms), `open_error_popup` (limesurvey
recipient), the `res.partner`-side `action_view_strikes` stat button (the
`attendance_session_header`-side twin is already tested), `action_limesurvey_delete_closed_confirmed`
(delete-confirmation redirect for closed surveys).

### Tier 0.5 — Portal frontend (customer-facing, reached via `@http.route`, not `ir.actions`)

A second, separate mechanical enumeration (2026-07-31, developer explicitly asked for this
scope to be included) of `controllers/*.py` found the **entire portal frontend has
effectively zero test coverage** — this is a different reachability mechanism than the
menu/action-based backend audit above (Odoo routes + QWeb templates under `views/portal/`,
not `ir.actions.act_window`/menuitems), so it needed its own pass. `static/tests/tours/*.js`
has zero references to any `/my/*` path — every one of the 63 existing tours targets `/odoo`
(backend) only.

**5 page-rendering routes, all with zero coverage of any kind:**

| Route | Renders | Purpose |
|---|---|---|
| `/my/gestion-matriculas` | `ems.portal_enrollment_confirmed` or `ems.portal_enrollment_process` (state-dependent) | The core student/family enrollment workflow — authorizations, items, payment term/method, comments. Highest-complexity controller logic in the whole module, entirely unrendered by any test. |
| `/my/documentacion` | `ems.portal_documentation` | Document center: submitted docs, bank info, benefit records, upload modals. |
| `/my/comunicaciones` (+ `/page/<int>`) | `ems.portal_communications` | Paginated communications history. |
| `/my/account` | `portal.portal_my_details` (EMS-overridden read-only) | Portal user's own profile page. |
| `/my/asistencia`, `/my/calificaciones` | `ems.portal_under_construction_page` | Placeholder pages. Lowest risk (trivial template) but still zero coverage. |

**~10 state-changing POST/GET action routes**, all zero coverage except one: `select_student`,
`portal_enrollment_authorize`, `portal_enrollment_confirm`, `portal_authorization_document`
(PDF serve), `portal_documentation_submit`, `portal_documentation_cancel`,
`portal_documentation_download` (file serve) — all **NONE**. `portal_documentation_renew_iban`
has partial coverage: `tests/test_portal_enrollment.py::TestPortalEnrollmentRenewIban` hits it
via plain `HttpCase.url_open()` (checks HTTP status + DB side effects, not rendered HTML) — the
closest thing to portal coverage anywhere in the suite today, and a reasonable pattern to
extend for the POST-only action routes; the page-rendering routes need genuine `start_tour()`
coverage (logged in as a portal user, not admin) to prove the page actually renders in a
browser, matching the same bar as the backend tours above.

This is materially new territory (no existing portal tour to copy conventions from) and
sizeable on its own (5 pages + ~10 actions) — treated as its own phase, not folded silently
into Tier 1/3 line items above.

### Out of scope for this pass

Nothing currently — backend (menus/actions/buttons/cog-menus/embedded views) and portal
(`@http.route`) are both now covered by this enumeration.

## Proposed order

1. **Fix the two navigation bugs** (menu id collision, xmlid collision) — cheap, unrelated to
   tours, currently-shipping defects.
2. **Tier 1**, in the order listed (client-action risk first, then the interlinked
   enrollment-proposal/applicants/no-destination cluster together since they share
   `ems.enrollment_proposal_wizard`, then the rest).
3. **Tier 0.5 (Portal)** — the 5 page-rendering routes first (proves each page renders at all
   for a real portal user), then the action routes, then extend the existing
   `renew-iban`-style `url_open` pattern to the other POST-only actions where a full browser
   tour isn't needed to prove no-crash (a page render deserves `start_tour`; a pure
   state-mutation endpoint can reasonably stay at the `url_open` bar, matching what already
   exists for `renew-iban`).
4. **Tier 2** (ASP secondary actions).
5. **Tier 3** (embedded tabs on already-covered forms).
6. Tier 4/5 left documented but not scheduled, matching the developer's own stated bar (isolated
   button/dialog failures are acceptable; whole-section failures are not).

Each item follows the same gate as every tour added today: `pylint --disable=all
--enable=redefined-builtin`, `./upgrade.sh`, scoped `./test.sh TestClassName`, one full
unscoped `./test.sh` at the end of the whole pass (not per item), changelog entry per item, this
file updated as items close.

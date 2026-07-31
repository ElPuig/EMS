# Full UI-coverage re-audit (v2) — every screen must render without crashing

**Status: ✅ CLOSED, 2026-07-31.** Every item in the "Proposed order" below is now done —
Tier 1, Tier 2, Tier 3, and the portal — and the full unscoped `./test.sh` is green (**0
failed, 0 error(s) of 1411 tests**, confirmed on a second full run after fixing one
full-suite-only flake found in the first run). This section is kept as the historical record
of why the previous "audit complete" declarations weren't trustworthy; per this plan's own
lifecycle rule (see `CLAUDE.md`'s "Design plans" section), this file should be deleted once its
still-useful content (the reusable gotchas, mainly) is confirmed folded elsewhere or the
developer confirms it's no longer needed — not done automatically here.

Supersedes the "audit complete" declarations from earlier today in this same file's history
(see git log) — those were wrong, twice, and this file was rewritten from scratch after a
proper mechanical re-audit rather than another manual enumeration pass.

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
| ~~9~~ | ~~Minutes~~ | ~~`action_minute_tree`~~ | **Not a gap, verified 2026-07-31**: its `<menuitem>` (`views/documentation/minutes/menu.xml`) has been commented out since the module's very first commit (`44bf088`), same for a whole notebook section in its form — deliberately unexposed, not a missed tour target. Skipped, per the developer's reminder to check for intentional hiding before treating something as a bug. |
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

## Execution log, 2026-07-31 — all items closed

Worked through the full order above in one pass (developer: "Sigue con todo, sin parar"),
pausing only once mid-pass when the developer flagged that some menus in this codebase are
deliberately hidden and asked to check before assuming a gap is a bug — see the
`menu_work_locations` finding below, confirmed via git history to be a genuine bug (existed
since the module's first commit, no deliberate-hiding marker anywhere), and the separate
`ems.minute`/Minutes finding, which turned out to be the deliberate-hiding case the developer
was right to ask about (its `<menuitem>` has been commented out since day one).

**Navigation bugs fixed (unrelated to tour coverage, found during the enumeration):**
1. `menu_work_locations` id collision — "Work locations" had no menu entry at all (silently
   overwritten by "Working schedules" due to manifest load order); renamed to
   `menu_hr_work_locations`.
2. `ems.action_student_form` xmlid collision — a dead, hardcoded `res_id=57` duplicate deleted;
   confirmed empirically that Odoo's data loader doesn't reset a field just because a later
   definition omits it (needed an explicit `eval="False"`).

**Tier 1 (13 whole screens) — 12 closed, 1 confirmed not a gap:**
`ems.grade_tutor_matrix`, the enrollment-proposal/graduation cluster, Preinscription,
Students without destination, Academic history (+ nested subject/outcome + partner tab),
Plannings, Import grades, Work placement evaluation (EM), Providers, Enrollments (config),
LimeSurvey Recipients tab, native `hr.attendance` form's EMS buttons — all now have tours.
**Minutes** (`action_minute_tree`) turned out to be deliberately unexposed (see above) — no
tour added, correctly skipped.

**Tier 2 (ASP secondary actions) — closed:** `ems_asp_crud`/`ems_asp_role_crud`. Found a real
EMS validation rule the hard way (`.o_field_invalid` DOM probe, since the save silently
no-opped with no visible dialog): `private_email` is required for a new teacher/ASP employee,
on a tab that isn't the default one.

**Tier 3 (6 never-clicked tabs on already-covered forms) — closed:** extended
`level_tour.js`/`study_tour.js`/`authorization_template_tour.js`/`group_tour.js`/
`withdrawal_tour.js`/`attendance_template_tour.js` in place rather than adding new tours.

**Portal (previously out of scope, added back in at the developer's request) — closed:**
5 page-rendering routes now have real browser tours logged in as a portal student user
(`portal_tour.js`); confirmed Odoo's tour-test JS loads on portal/website pages the same way
it does on the backend. Found this dev DB's portal users default to Catalan, so English-text
`:contains()` triggers silently never match — switched to structural (icon/class) selectors,
same discipline already used for language-independent backend status buttons. The remaining
~10 state-changing action routes got `url_open`-based checks (`test_portal_actions.py`)
instead of full tours, matching the plan's own stated bar (a page render deserves a tour, a
pure POST/GET action endpoint doesn't).

**Final gate:** full unscoped `./test.sh` — first run found one genuine flake
(`ems_em_grading_wizard_apply`, visible only under full-suite load: ending the tour immediately
after "Apply changes" could race the matrix's own DB reload, tripping Odoo's "form left in
edition mode" check). Fixed by waiting for the applied value to be confirmed post-reload before
ending the tour. Second full run: **0 failed, 0 error(s) of 1411 tests.**

Remaining, explicitly non-blocking (documented, not scheduled): Tier 4 (cog-menu buttons whose
target wizard is already tested via direct URL) and Tier 5 (isolated popups/buttons) from the
original tiering above, plus the still-standing Esfera-xlsx full-import gap from the previous
audit round.

## Update, 2026-07-31 (later same day) — Tier 4 closed, Tier 5 partially closed

Developer said "vale, ponte con eso" (go ahead) after this file's own "documented, not
scheduled" framing for Tier 4/5. Worked through both:

**Tier 4 (3 cog-menu click paths) — closed.** Extended
`applicant_import_wizard_tour.js`/`student_import_wizard_tour.js`/
`student_update_wizard_tour.js` in place: each now opens its wizard via the real cog-menu
click (`.dropdown-item:contains('...')` — a raw `<DropdownItem>` renders Bootstrap's own
class, not Odoo's `.o_menu_item`, same gotcha as `working_schedules_import_wizard_tour.js`)
instead of a direct URL to the wizard's own action. All three passed first try.

**Tier 5 — 1 of 4 items closed, 3 left as documented/not-scheduled (matches this file's own
stated bar: isolated button/dialog failures are acceptable).** Added a fourth leg to
`strike_tour.js` (`ems_strike_partner_stat_button`) covering the `res.partner`-side
`action_view_strikes` stat button (`views/community/contact/form.xml`) — the
`attendance_session_header`-side twin was already tested, this one wasn't. Hit and fixed a
genuine tour-authoring bug along the way, not an app bug: after `.o_switch_view.o_list`, the
search box must not be touched until an explicit `.o_list_view` wait step confirms the
kanban→list transition finished — typing into the search input immediately after the click
races the search bar's own remount and the typed text is silently lost (compare
`portal_access_wizard_tour.js`, which already has this wait step; my first attempt omitted it
and the search silently no-opped, 1111+ real students in this dev DB meant the un-searched
target was never on page 1). Left **not scheduled**, matching this file's own tiering
rationale: `open_exception_popup` (attendance_issue/notice forms — would need constructing a
`queue.job` fixture with `exc_info` set, disproportionate effort for an isolated error-detail
popup), `open_error_popup` (limesurvey recipient, same shape), `action_limesurvey_delete_closed_confirmed`
(exercises Odoo core's own generic `RedirectWarning` dialog mechanism, not EMS view code).

Gate: `pylint --disable=all --enable=redefined-builtin` clean, `./upgrade.sh` clean, each
touched test class passed scoped, full unscoped `./test.sh` run as the final gate for this
update (see changelog for the result).

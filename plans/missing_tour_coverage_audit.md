# PLAN — Audit and fill missing browser tour coverage across EMS

> **Status: in progress, started 2026-07-30.** Requested by the developer after a concrete
> incident: a checkbox-to-radio widget change on `ems.limesurvey_block`'s form
> (`plans`/memory: `limesurvey_block_special_mutual_exclusion_asymmetry`, now resolved) was
> initially shipped with no tour, on the reasoning "no tour exists for this view" — which
> is itself the gap, not a reason to skip verification. Adding the tour afterward (per the
> developer's explicit ask) caught two real, non-trivial browser-only bugs that no amount of
> `./upgrade.sh`/`TransactionCase` testing would ever have surfaced (see below). This plan is
> the systematic follow-up: how many other views are in the same unverified state, and what
> order to close them in.
>
> Lives under `plans/` per `CLAUDE.md`'s "Design plans" convention — delete once the audit is
> complete and either every gap is closed or explicitly triaged/deferred with reasoning
> recorded somewhere durable (this file, or the relevant model's dev doc).

## Why this matters (not just a coverage-percentage nit)

`./upgrade.sh` succeeding only proves a view's XML is structurally valid — every field
referenced exists on the model, every widget is compatible with its field's type (Odoo
validates this on every module load/upgrade, not just in test mode). It proves **nothing**
about whether the page actually renders correctly in a browser, or whether an interaction a
user would actually perform (click, type, select) works. `TransactionCase` tests never touch
the browser/OWL layer at all. Only an `HttpCase` tour, run through Odoo's real headless-Chrome
test harness, catches that class of bug.

**Concrete proof this isn't theoretical:** writing the first tour for `ems.limesurvey_block`
(2026-07-30) immediately caught two bugs that had shipped invisibly:
1. `run: "select students"` on a plain Selection `<select>` silently failed to select
   anything — Odoo's `SelectionField` widget JSON-stringifies the option `value` attribute
   (`stringify(option[0])`), so the raw selection key never matches. The **existing, already-
   shipped** `target` field on this exact form has had this same widget type since before this
   pass — meaning the header form's Target field may have been just as fragile to certain
   interactions, just never actually driven by anything that would have revealed it.
2. `tsv_raw_text` (`widget="code"`, used on both the header and block forms, and potentially
   elsewhere) renders via the Ace editor library — its real input element is a deliberately
   invisible textarea that the tour engine's generic `edit` action can't drive at all;
   filling it requires calling into the global `ace` object directly.

Neither of these is specific to the `special_type` change — they're pre-existing
characteristics of widgets used **elsewhere in the module** too. Any other view using
`widget="code"` or being driven through a `<select>` in a not-yet-written tour is an unknown
until it's actually tested.

## Rough scope (quick count, 2026-07-30 — not a precise audit)

- 26 tour files currently exist (`static/tests/tours/*.js`).
- 72 distinct `ir.actions.act_window` ids are defined across `views/`.
- 52 files under `views/` contain at least one `<form>`.

Even accounting for actions that share a tour, or models genuinely covered indirectly through
another model's tour (e.g. an embedded one2many form, like `ems.limesurvey_block` itself used
to be before 2026-07-30), this suggests a large fraction of the module's form/list/kanban
surface has never been driven by a real browser. The exact list needs the actual audit below,
not this rough count.

## Proposed approach

1. **Enumerate real gaps**, not just a file-count mismatch: for every model with a view
   (`grep` `<form>`/`<list>`/`<kanban>` under `views/`), check whether it's reachable from an
   *existing* tour — either as the tour's own primary target, or embedded inside another
   model's form (matching the "secondary/embedded view" requirement already in `CLAUDE.md`'s
   Development workflow). Produce a concrete list of models/views with **zero** tour coverage
   today — this is real, non-trivial exploration work, likely worth delegating to an `Explore`
   agent given the breadth (many files, cross-referencing views against tour files).
2. **Triage, don't blanket-fix**: not every gap is equally worth closing immediately — a
   rarely-touched admin config screen is lower priority than a screen teachers/families use
   daily. Group the findings by rough priority (role-facing frequency, complexity of the view,
   whether it's read-only/reference data vs. something users actively edit) rather than
   working through them alphabetically.
3. **Fix incrementally**, one model/view at a time, each as its own small Red-Green cycle
   (write the tour, confirm it currently would have nothing to catch since the view isn't
   changing, but still run it to prove the view itself renders and basic interactions work) —
   not as one giant PR. Reuse the two gotchas found above (`selectByLabel` for plain
   `<select>`s, `ace.edit(anchor).setValue(...)` for `widget="code"`) rather than
   rediscovering them per file.
4. Going forward, per the now-updated `CLAUDE.md` Development workflow: **any new change to a
   model with a UI surface gets a tour as part of that same change**, closing off new gaps
   from accumulating while this backlog is worked through.

## Audit findings (Explore agent, 2026-07-30) and progress

Full enumeration came back as: 25 tour files / 35 registered tours vs. 64 `ir.actions.act_window`
records total, only 24 opened directly by a tour URL — roughly **~40 hard zero-coverage
model/view surfaces**, ~6 soft/partial. Priority order agreed with the developer (highest-risk/
highest-value first, custom widgets and daily-use screens ahead of reference/config data):

1. ✅ **`ems.grade_session`** (`action_grade_session_tree`, custom `widget="grade_matrix"`) —
   done 2026-07-30. `static/tests/tours/grade_matrix_tour.js` +
   `tests/test_grade_matrix_tour.py`. Unlike the `ems.limesurvey_block` precedent, this pass did
   **not** surface a pre-existing application bug — every failure hit while writing the tour
   turned out to be a test-authoring mistake (an `HttpCase`-internal `self.session` naming
   collision, `ems.group.name` being a silently-overwritten computed field, a CSS
   `:first-of-type` misunderstanding, an empty-`<span>` visibility check, and OWL's async
   DOM-patch timing after a raw `dblclick` needing a poll loop instead of one
   `requestAnimationFrame`). It does positively confirm the grid's double-click → edit → Apply
   → re-render flow works correctly in a real browser, which had never been verified before.
2. ✅ **`ems.portal.access.wizard`** (`widget="radio"` on `mode`) — done 2026-07-30.
   `static/tests/tours/portal_access_wizard_tour.js` + `tests/test_portal_access_wizard_tour.py`.
   Drives the real UI path (select a student in the list, open the list's Actions/cog menu,
   launch the wizard, switch the radio to "Revoke access", Apply), asserting the underlying
   portal user is actually archived afterward. Found one genuine, non-trivial gotcha along the
   way: Odoo's tour-engine `:contains()` is case-insensitive, so a menu-item selector text
   ("Portal access") ambiguously matched both this action and the unrelated, native Odoo
   action already on the same list ("Grant Portal Access") — fixed in the tour by matching on
   a substring unique to this action's name ("students/families"). Also flagged (not fixed) as
   a real UX finding: the same ambiguity exists for a human reading the Actions menu, not just
   the tour's selector — two similarly-worded, unrelated portal-access entries sit side by
   side on the same list.
3. ✅ **`ems.grade_session_state_wizard`** (`widget="radio"` sibling of `grade_session_wizard`,
   itself only ever smoke-tested) — done 2026-07-30.
   `static/tests/tours/grade_session_state_wizard_tour.js` +
   `tests/test_grade_session_state_wizard_tour.py`. Switches mode from the default "By study"
   to "By level", picks a level via many2many_tags autocomplete, applies a real evaluation
   state transition, verified against the DB. Found one real, reusable gotcha: a `target="new"`
   dialog's own `<footer>` is a DOM sibling of `.o_form_view`, not nested under it — a
   `.o_form_view footer ...` selector (fine on a directly-navigated page) silently never
   matches inside a dialog; use `.modal footer ...` for any dialog-rendered form's footer
   buttons instead.
4. ✅ **`action_ems_enrollments`** (`sale.order`, the matrícula screen) — done 2026-07-30.
   `static/tests/tours/enrollment_tour.js` + `tests/test_enrollment_tour.py`. Opens a seeded
   draft enrollment, walks the three EMS-added tabs (Enrollment Items / Authorizations /
   Payment) to confirm none crash despite the form's heavy xpath customization over native
   Sales, and does a real edit-save (the `shift` field) verified against the DB. No pre-
   existing bug found — confirms the form renders and saves correctly.
5. ✅ **`ems.notice`** (`action_communication_list`, `widget="html"` + `statusbar` +
   `many2many_tags`) — done 2026-07-31. `static/tests/tours/notice_tour.js` +
   `tests/test_notice_tour.py`. Creates a real notice end-to-end (group selection, auto-
   populated recipient list, rich-text message, save, "Send now" through to a real `state`
   transition), verified against the DB. Never risks a real send — `with_delay()` only queues
   a `queue.job` row in a normal test run. Found one reusable gotcha: the tour engine's generic
   `edit` action can't fill a `widget="html"` contenteditable div (`isEditable()` only
   recognizes `<input>`/`<textarea>`) — Odoo's own tour engine has a dedicated
   `run: "editor <text>"` action for exactly this (see `mail`'s composer tours), used here
   instead.
6. ✅ **Attendance office screens** (`ems.attendance_correction`/`_issue_*`/`_justification`)
   — done 2026-07-31. Three tours: `static/tests/tours/attendance_correction_tour.js` +
   `tests/test_attendance_correction_tour.py` (opens a pending request, accepts it, verifies
   the underlying `hr.attendance` was corrected); `attendance_justification_tour.js` +
   `test_attendance_justification_tour.py` (walks all three read-only tabs of a seeded
   justification, edits+saves Notes — creating a NEW one via UI needs `widget="daterange"`,
   deliberately left for a future pass); `attendance_issue_tour.js` +
   `test_attendance_issue_tour.py` (pure render smoke test, tutor level + drill into
   student/session detail — every view here is read-only by design). Two reusable gotchas
   found: the arch's `<header>` tag compiles to `.o_form_statusbar`, not a literal `<header>`
   element (`.o_form_view header ...` silently never matches); and the `HttpCase`-internal
   `self.session` naming collision (see item 1) recurred with a fixture also named
   `cls.session`.
7. ✅ **File-upload wizards** (`ems.working_schedules_import_wizard` `many2many_binary`,
   `ems.applicant_import_wizard`/`student_import_wizard`/`student_update_wizard` `binary`) —
   done 2026-07-31. Four tours using Odoo's `inputFiles()` test helper (the generic tour
   `edit` action can't drive a file `<input>` at all): `applicant_import_wizard_tour.js`
   (real CSV upload, full successful import verified against the DB);
   `working_schedules_import_wizard_tour.js` (XML upload via the cog-menu entry, verifies
   the unknown-teacher blocking-error path); `student_import_wizard_tour.js` (a minimal but
   structurally real xlsx, embedded as base64 since a valid xlsx is a zip container that
   can't be hand-authored as a plain string, deterministically hits the "missing required
   columns" error dialog — a full successful Esfera-format import deliberately left for a
   future pass, same judgment call as the daterange widget in item 6);
   `student_update_wizard_tour.js` (CSV upload + column mapping + real student update).
   Reusable gotchas found: OWL doesn't sync an `<input>`'s live value to its HTML `value`
   attribute (use hoot-dom's `:value()` pseudo-class, not `[value=...]`); a custom cog-menu
   item built directly from `<DropdownItem>` renders as `.dropdown-item`, not the standard
   `.o_menu_item`; a tour that leaves a dialog open in edition mode must explicitly close it.
8. ✅ **`res.config.settings`'s EMS Management tab** (~20 fields: Google Workspace, LimeSurvey
   credentials, course/attendance/strike settings) — done 2026-07-31.
   `static/tests/tours/settings_tour.js` + `tests/test_settings_tour.py`. Switches to the EMS
   tab, edits one representative field per block (proving the tab renders and its fields are
   genuinely interactive), then Discards rather than Saves. Deliberately does not exercise
   Odoo's Save/reload mechanism: `res.config.settings.execute()` returns a real browser
   navigation (`{'type': 'ir.actions.client', 'tag': 'reload'}`), which destroys the tour
   macro's own JS execution context — no following step can reliably observe anything after
   it (confirmed empirically via two different race/timeout failures before landing on
   Discard instead). That's core Odoo behavior, not an EMS-specific gap.
9. Lower priority (reference/config data, plain widgets):
   - ⏭️ **`ems.tracking`/`ems.minute` — skipped, 2026-07-31**, developer's explicit call.
     Both have zero reachable UI entry point today: `ems.tracking`'s standalone action has no
     menuitem anywhere and its own `ems.study.follow_ids` One2many is never embedded in any
     view; `ems.minute`'s menuitem is commented out in `views/documentation/minutes/menu.xml`.
     Writing a tour for a screen no real user can reach isn't a meaningful coverage gap to
     close - if either is ever wired up (or confirmed dead like `ems.record` was), revisit.
   - ✅ **`hr.job`, `hr.work.location`, `hr.contract.type`, `ems.strike.reason`,
     `resource.calendar` (Schedule Frameworks), `product.template` (enrollment items),
     `sale.order.template` (enrollment templates), `ems.authorization.template`, `queue.job`
     (attendance notifications), `account.move.line` (enrollment collections),
     `mail.activity.type` (task assignment), and the "Families" filtered `res.partner`
     screen** — done 2026-07-31, all twelve as plain create/edit or render-only smoke tours
     (`job_tour.js`, `work_location_tour.js`, `employment_type_tour.js`,
     `strike_reason_tour.js`, `schedule_framework_tour.js`, `enrollment_items_tour.js`,
     `enrollment_template_tour.js`, `authorization_template_tour.js`,
     `attendance_notification_tour.js`, `enrollment_collections_tour.js`,
     `task_assignment_tour.js`, `family_tour.js`, each with a matching `tests/test_*_tour.py`).
     One real, non-tour-specific finding along the way: `hr.job`'s EMS-added
     `employee_type`/`group_id` fields turned out unreachable through the form (sit inside
     native hr.job's hardcoded-`invisible="1"` "Recruitment" page) — confirmed CSV-only by
     design via `data/cat/hr.job.csv`, not a bug, tour scoped down accordingly. Several
     reusable gotchas: `hr.job` and `product.template`'s native `name` fields (and one of
     `res.partner`'s two conditional name fields) render via `widget="text"` (a `<textarea>`),
     not a plain Char `<input>`; EMS's own `res.partner` form splits name into separate
     `firstname`/`lastname` inputs (the `partner_firstname` convention); Odoo's list view
     binds its row-open click handler to a data cell, not the bare `<tr>`.

Working the same one-gap-at-a-time cadence as the rest of this branch's DTON work — each item
gated with `./upgrade.sh` + its own scoped `./test.sh TestClassName`, changelog entry appended
per item, full unscoped `./test.sh` deferred until a batch is done rather than run after every
single tour.

**Batch gate, 2026-07-30 (items 1-4 above):** full unscoped `./test.sh` run —
0 failed, 0 error(s) of 1359 tests. No regressions from any of the four tours added in this
batch.

**Batch gate, 2026-07-31 (items 5-8 above — the full priority list is now complete):** full
unscoped `./test.sh` run — 0 failed, 0 error(s) of 1368 tests. No regressions from any of the
tours added in this second batch (`ems.notice`, the three attendance office screens, the four
file-upload wizards, and `res.config.settings`).

**Batch gate, 2026-07-31 (item 9 — the entire audit backlog is now complete except the two
explicitly-skipped orphaned models):** full unscoped `./test.sh` run — 0 failed, 0 error(s) of
1380 tests. No regressions from any of the twelve tours added in this final batch.

**Addendum, 2026-07-31 (post "audit complete"):** the developer asked specifically whether
student attendance — described as the module's single most-used area — was actually fully
covered. It was not: `ems_attendance_session_view` (the "Current" roll-call client action,
bound to the app's own root menu) had its strike-issuing flow covered via `strike_tour.js`,
but never its actual core action — marking a student's attendance status — nor starting a new
session from a planned schedule slot. ✅ **Closed** via
`static/tests/tours/attendance_passlist_tour.js` +
`tests/test_attendance_passlist_tour.py`: opens a planned schedule, starts the session,
marks a status (by DOM column position, since status buttons only expose a translated name,
no stable id), adds a note, all verified against the DB. Along the way, confirmed with the
developer (not a bug, expected): `create_scheduled_session()` derives `session_teacher_id`
from whoever clicks "Start session" rather than the schedule's actual assigned teacher, so a
non-teacher account (e.g. a pure admin) gets a hard "mandatory field not set" error — the
tour logs in as a seeded teacher user instead of admin, matching real usage. This is a
reminder that this plan's own "hard zero-coverage" enumeration (Explore agent, 2026-07-30)
was a one-time snapshot, not guaranteed exhaustive — worth spot-checking the highest-traffic
areas specifically before considering the audit truly done, rather than trusting the original
count alone.

**Addendum, 2026-07-31 (second gap found during the same attendance spot-check):** while
closing the roll-call gap above, found that `ems.attendance_template` (the weekly recurring
class schedule setup screen the roll-call depends on) also had no real coverage beyond a
shallow color-widget smoke test — its own "Sessions" embedded one2many tab and its
`widget="daterange"` `start_date`/`end_date` fields had never been driven end-to-end. The
developer said "Sigue" to close this one too rather than leave it deferred. ✅ **Closed** via
`static/tests/tours/attendance_template_tour.js` + `tests/test_attendance_template_tour.py`:
fills every field of a new template, adds a schedule line in the embedded list, saves, and
verifies both the template and its schedule against the DB. This also **resolves the
`widget="daterange"` open question** noted below and in `attendance_justification_tour.js`'s
own deferral comment — the widget works correctly with a plain tour `edit` action on
`input[data-field='start_date'/'end_date']`, no special handling needed; it's built on the
standard `DateTimeField` component. The stale in-code
`TODO: not working, check how its solven at justification form` comment on this field
(`views/attendance/attendance_template/form.xml`) is now confirmed outdated.

**Batch gate, 2026-07-31 (both attendance addenda above):** full unscoped `./test.sh` run —
0 failed, 0 error(s) of 1382 tests. No regressions from either of the two tours added in this
attendance-focused sub-batch (`attendance_passlist_tour.js`, `attendance_template_tour.js`).

**Addendum, 2026-07-31 (third gap, closed same day):** since `widget="daterange"` was now
confirmed working, the developer chose to also close `ems.attendance_justification`'s own
still-deferred "create new" flow rather than leave it pending. ✅ **Closed** via a new
`ems_attendance_justification_create` tour appended to the existing
`attendance_justification_tour.js` (+ a matching test method in
`tests/test_attendance_justification_tour.py`): fills `teacher_id` (whose onchange populates
the `student_id` domain), `student_id`, and the date range, then saves, verified against the
DB. Found a second daterange variant along the way — this form puts `widget="daterange"` only
on `start_date` (with `options="{'end_date_field': 'end_date'}'"`), so *both* date inputs
render inside that one field's own widget container rather than as two separate field widgets
like `ems.attendance_template` — and that the typed value is stored exactly as typed in UTC,
regardless of the logged-in user's own `res.partner.tz`, since the headless test browser's own
(UTC) system timezone is what the client-side parsing actually uses.

**Batch gate, 2026-07-31 (this third addendum):** full unscoped `./test.sh` run — 0 failed,
0 error(s) of 1383 tests.

**Status: audit complete, 2026-07-31.** Every identified hard-zero-coverage model/view surface
now has a tour, except `ems.tracking`/`ems.minute` (explicitly skipped — see item 9, no
reachable UI entry point today) and one remaining deliberately-deferred sub-scope (a full
successful Esfera-xlsx student import in item 7's `student_import_wizard_tour.js`) — left as a
documented, non-blocking gap for a future pass rather than a reason to hold up this branch. Per
this plan's own "Design plans" lifecycle (see `CLAUDE.md`), this file should be deleted once
its content is folded into durable documentation (or the developer confirms the working notes
above are no longer needed) — not yet done as of this entry.

## Open questions

1. Should this be one large sweep, or folded opportunistically into whatever model each future
   session happens to be touching anyway (mirroring how the original DTON rollout worked
   model-by-model)? The DTON rollout precedent suggests the latter is more sustainable, but
   the developer may want a dedicated push instead.
2. Is there a way to make "view has no tour" mechanically checkable (e.g. a script comparing
   `views/` against `static/tests/tours/`) so this doesn't silently regress again, or is manual
   vigilance (now reinforced in `CLAUDE.md`) enough?

## Where this is also documented

Not yet documented elsewhere — this plan is the only record until the audit produces
per-model findings worth folding into individual dev docs.

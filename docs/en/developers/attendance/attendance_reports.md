# Technical Reference: Attendance reports

## Overview

Three printable PDF report variants over `ems.attendance_session_line` — by group, by student, by subject —
driven by a **single unified wizard** (`ems.attendance_report_wizard`) with a `report_type` selector, plus a
self-service **Attendance reports** pivot/graph screen. **Attendance → Reports** opens the pivot/graph
screen directly (pivot by default); the PDF wizard is reachable from its header's ⚙ Actions menu (one
"Attendance report" entry), not from a separate menu entry. The 3 variants were originally 3 separate
wizard models/views/actions; they were later merged into one (see "Unification" below).

**Trigger for this change:** the 3 PDF wizards (`ems.attendance_report_{group,student,subject}_wizard`)
used raw `cr.execute()` SQL against physical table/column names to fetch report data and to filter their
dropdowns. This broke silently on model renames (it already happened once, during the `status` →
`status_id` migration — see [ems.attendance_status](attendance_status.md)), and one wizard built its query
via unparameterized string interpolation. All SQL was replaced with ORM calls, and a native pivot/graph
screen was added so staff can explore data themselves instead of being limited to the 3 fixed PDF layouts.
The pivot/graph screen initially shipped with a 4th, "Attendance analysis" list view and its own menu
entries for the 3 wizards; both were folded away shortly after (see "Attendance reports" section below) once
actual usage showed the list added no value and the wizards read better as quick actions on the analysis
screen than as separate menu items.

**Module files:** `models/attendance/attendance_reports.py`, `models/attendance/attendance_session.py`
(new stored fields on `ems.attendance_session_line`), `views/attendance/attendance_reports/{wizard,menu,analysis_views}.xml`,
`reports/attendance/{group,student,subject}.xml` + `reports/attendance/templates/{sumary_table,details_table,detail_section}.xml`,
`static/src/js/backend/attendance_report_analysis_cog_menu.js` +
`static/src/xml/backend/attendance_report_analysis_cog_menu.xml`.

---

## Data model

```mermaid
erDiagram
    ems_attendance_session_header ||--o{ ems_attendance_session_line : "attendance_session_id"
    ems_attendance_session_line }o--|| ems_attendance_status : "status_id"
    ems_attendance_session_line }o--o| res_partner : "student_id"
    ems_attendance_report_wizard ..> ems_attendance_session_line : "print() -> status_ids (per report_type)"
```

The single `ems.attendance_report_wizard` carries a `report_type` selector (`group` / `student` / `subject`)
and the union of the 3 variants' fields; only the ones relevant to the chosen type are shown/required. Its
`print()` dispatches to one of the 3 `ir.actions.report` (unchanged) by `report_type`; the 3 report
data `AbstractModel`s (`report.ems.attendance_report_{group,student,subject}`) all `browse` this one wizard
and share a single `_build_report_values(env, docids, data, group_key)` helper (they differ only in the
`group_key` used to group the per-line entries — student for by-subject, subject for by-group/by-student).

`ems.attendance_session_line` gained 5 stored `related` fields, copied from `attendance_session_id` purely
so the analysis pivot/graph can `GROUP BY` them without a join: `date`, `level_id`, `study_id`, `group_ids`,
`subject_id`. `group_ids` is a related Many2many with `store=True`, which needs its own explicit
`relation`/`column1`/`column2` (Odoo cannot auto-derive a relation table name for a *related* Many2many the
way it does for an owned/computed one) — see `relation="ems_attendance_session_line_group_rel"` in
`attendance_session.py`.

It also gained `absence_rate` (`Float`, `compute`+`store`, `aggregator="avg"`): `100.0` if
`status_id.category == 'absence'` else `0.0`. Storing 0/100 rather than a boolean means the graph view's
`avg` aggregation resolves directly to a percentage — no separate widget/formatting needed. Odoo 18 field
API uses `aggregator` (replaces the pre-18 `group_operator`); pivot/graph and `read_group` calls pick it up
automatically once the field is used as a measure.

---

## Wizards: SQL → ORM

Each wizard has 2 responsibilities, both formerly raw SQL, now plain ORM:

| Wizard | Dropdown filter (`allowed_*_ids`) | `print()` |
|---|---|---|
| `..._group_wizard` | `env['ems.teaching'].search([('teacher_id', '=', current_teacher.id)]).mapped('group_id')` (no study filter — see "Wizard simplification" below) | `env['ems.attendance_session_line'].search([('attendance_session_id', 'in', session_ids)])` |
| `..._student_wizard` | enrollments whose `(group_id, subject_id)` matches one of the teacher's `ems.teaching` pairs (no group filter anymore — see "Wizard simplification" below) | `search([('student_id', '=', ...), ('attendance_session_id.date', '>=', from), ('attendance_session_id.date', '<=', to)])` (dot-notation domain, no manual join) |
| `..._subject_wizard` | `allowed_subject_ids`: teacher's own taught subjects (no group filter — see "Wizard simplification" below); `allowed_group_ids`: `env['ems.teaching'].search([('subject_id', '=', subject_id), ('teacher_id', '=', current_teacher.id)]).mapped('group_id')` | domain now `("group_ids", "in", self.group_ids.ids)` (was `self.group_id.id` singular) |

The `current_teacher.id > 1` admin-bypass check (an existing convention: any user with no `hr.employee`
record, or whose employee id is 1, sees unfiltered data) was preserved as-is — not in scope to change.

**Two pre-existing bugs were fixed while porting this code**, not just carried over:
1. `allowed_group_ids` never actually filtered by `study_id` despite triggering on it — it returned every
   group the teacher taught, regardless of study. Fixed by adding `('group_id.study_id', '=', study_id)` to
   the domain.
2. `allowed_subject_ids` appended the `group_id` domain tuple a second time by mistake instead of adding a
   `teacher_id` filter, so non-admin teachers saw every subject taught in the group by *any* teacher, not
   just their own.

**A third, unrelated pre-existing bug surfaced only by the new tour** (not caught by any unit test, nor
by a clean `./upgrade.sh` — exactly the gap DTON's tour requirement exists to close): all 3
`_get_report_values(docids, data=None)` methods did `if len(docids) == 0: docids = data['doc_ids']`, but
`docids` is always `None` (never `[]`) on the real call path — the wizards call
`report_action(None, data=data)`, and `report_action()` never sets `active_ids` when its `docids` argument
is falsy, so the controller always invokes `_get_report_values(None, data=data)`. `len(None)` raised
`TypeError`, so **every PDF actually failed to generate** — invisible to `TransactionCase` tests (which
call `print()` and only inspect the returned action dict, never actually render the report) and to
`./upgrade.sh` (which never renders a report either). Fixed by using `if not docids:` instead, which
handles `None` the same as `[]`. The `# TODO` comment already on that line (*"Always null even when
setting up at report_action"*) shows a previous developer had already noticed the symptom without tracing
it to this line.

**Not a security fix:** `ir.rule` (`security/rules/attendance.xml`) already grants every teacher
unrestricted read on `ems.attendance_session_line` (`rule_attendance_session_line_teacher_all_read`,
`domain_force=[]`) — deliberately, so tutors can see justification-relevant data across sessions they don't
own. The wizard-side scoping above is UX convenience (don't overwhelm a teacher's dropdown with groups/
subjects/students they don't teach), not a security boundary; it was never enforced by `ir.rule` and still
isn't after this change.

### Wizard simplification: all 3, done incrementally

The 3 wizards originally all shared the same level → study → group/student/subject cascade. They were
simplified one at a time, by explicit request, each requiring a sign-off before moving to the next:
by-group first, then by-student, then by-subject.

- **By group**: `level_id`/`study_id` removed, `group_id` is now the only selection step; `tutor_id`/
  `from_date`/`to_date` still auto-fill from it exactly as before.
- **By student**: `level_id`/`study_id`/`group_id` all removed, `student_id` is now the only selection
  step. `tutor_id` used to be `related="group_id.tutor_id"`; with `group_id` gone it's now
  `related="student_id.tutor_id"` — `res.partner` already carries its own `tutor_id`
  (`related="main_group_id.tutor_id"`, `models/contacts/contact.py:69`), so this is a one-line change, not
  a new lookup. `allowed_student_ids` used to scope to enrollments in *one* group (the one the user had
  already picked) whose subject the teacher taught there; with no group step first, it now has to check
  the teacher's *entire* teaching load: build the `{(group_id, subject_id), ...}` pairs from all of the
  teacher's `ems.teaching` rows, pre-filter `ems.enrollment` by `group_id in <those groups>` (cheap, SQL
  level), then `.filtered()` in Python for an exact `(group_id, subject_id)` pair match — a plain
  `('subject_id', 'in', ...)` domain would have been wrong, since it would match a student enrolled in a
  *different* group for a subject the teacher happens to teach elsewhere.
- **By subject** (the one that changed shape, not just lost fields): `level_id`/`study_id`/the old single
  `group_id`/`tutor_id` are gone; `subject_id` is now the only *selection* step, but it drives two new
  fields instead of just filtering the next one:
  - `group_ids` (`Many2many`, editable): pre-filled by `_onchange_subject_id` with *every* group where the
    current teacher teaches that subject (`ems.teaching` rows matching `subject_id` + `teacher_id`) — the
    user can remove entries afterward (tags widget), but its `domain` is still wired to `allowed_group_ids`
    (same `@api.depends('subject_id')` pattern as `allowed_subject_ids`→`subject_id` elsewhere) so re-adding
    one is restricted to the same allowed set, not a free-for-all.
  - `tutor_ids` (`Many2many`, read-only, informational): the distinct tutors of whatever's currently in
    `group_ids`. **Cannot be a `related="group_ids.tutor_id"` field** — Odoo raised `TypeError: Type of
    related field ... is inconsistent with ems.group.tutor_id` at `_auto_init` (a related chain through a
    Many2many to a trailing Many2one doesn't auto-promote to Many2many the way `store=True` related M2M
    fields do elsewhere in this file for `ems.attendance_session_line.group_ids`). Needed an explicit
    `compute='_compute_tutor_ids'` (`@api.depends('group_ids.tutor_id')`) instead — one line
    (`wizard.tutor_ids = wizard.group_ids.tutor_id`), since reading a Many2one field off a multi-record
    recordset already returns the deduplicated aggregate in the ORM.
  - `print()`'s domain changed from `("group_ids", "in", [self.group_id.id])` (singular) to
    `("group_ids", "in", self.group_ids.ids)` (the multi-select). The PDF template's header
    (`reports/attendance/subject.xml`) used `o.group_id.display_name` — switched to
    `', '.join(o.group_ids.mapped('display_name'))` via `t-esc` (no `t-field` equivalent for joining a
    recordset's names).
- All 3 use the same 2×2-ish layout: `<group col="2">` with nested single-field `<group>` elements (not
  plain `<field>` inside one `<group col="4">` — that renders one field per row instead of 2-per-row;
  confirmed by screenshot, see `views/planning_grading/grading/form.xml` for another in-repo example of the
  working pattern). By-group/by-student: row 1 is the main field + its related tutor, row 2 is
  `from_date`+`to_date`. By-subject needed 3 full-width rows first (`subject_id`, then `group_ids` tags,
  then `tutor_ids` tags — `colspan="2"` on each nested group) before the same `from_date`/`to_date` row.

Two things worth knowing, useful beyond just this feature:

- **The selection field's domain must be wired to its `allowed_*_ids`** (e.g.
  `domain="[('id','in', allowed_group_ids)]"`) — previously it wasn't for `group_id`: the original view
  filtered it only via `('study_id', '=', study_id)`, and `allowed_group_ids`/`_compute_allowed_group_ids`
  existed but were never actually referenced by any view domain (dead code). Removing the level/study
  fields removes whatever filter they provided, so wiring the `allowed_*_ids` field in is what makes the
  dropdown teacher-scoped *at all* now — not a regression, but the first time these compute results
  actually reach the UI.
- **A compute field with only `@api.depends_context('uid')` (no dependency on a real field) is not reliably
  computed on a freshly-created record** — confirmed empirically both in `TransactionCase` tests (reading
  `wizard.allowed_group_ids`/`allowed_student_ids`/`allowed_subject_ids` right after `.create({})` returned
  empty; calling `wizard._compute_allowed_*_ids()` explicitly fixed it) and in the browser tour (the
  dropdown showed no matches at all, so typing the seeded record's name fell through to the "Create new"
  quick-create suggestion instead — a full "Create Group" form dialog appearing in a failure screenshot was
  the tell). Since there's no other field left to hang an `@api.onchange` off once level/study/group are
  gone, the fix is a `default_get()` override that populates the `allowed_*_ids` field directly —
  `default_get()` is reliably called by the web client when opening a new wizard form, unlike the
  compute-on-access path. The compute method (still `@api.depends_context('uid')`) stays as a fallback for
  any other access path (e.g. server-side code creating the wizard directly), sharing the actual lookup
  logic via a small `_get_allowed_*_ids()` helper so it isn't duplicated between the two. Note
  `allowed_group_ids` on the by-subject wizard *doesn't* need this trick — it genuinely depends on a real
  field (`subject_id`), so plain `@api.depends('subject_id')` is reliable on its own; only the
  context-only `allowed_subject_ids` there needed the `default_get()` workaround.
- **Tour flakiness after a `Print` click ("Tour finished with an open form view in edition mode")**
  recurred across more than one of these wizards' tours (same class of flake as `TestWithdrawalTour` —
  click-vs-reflow contention, not a real bug: every tour step had already matched by the time it fired).
  Fixed the same way: `step_delay=300` on all 4 `start_tour()` calls in
  `tests/test_attendance_reports_tour.py`.

### By-subject wizard: opt-in per-student detail (`detail_status_ids`/`include_strikes`)

**The problem.** The by-subject PDF's "Students" section prints one full "Details" table per student —
every single session line for that student, unfiltered — with a forced page-break after each student. For
a subject taught across several large groups over a long date range this is a lot of unaggregated rows fed
to wkhtmltopdf (single-threaded, memory-heavy, and known to struggle with many forced page-breaks): a real
case with 182 sessions / 4725 lines / 59 students triggered a memory/row-count failure generating the PDF.
The "Summary" section (percentages, via `_report_data`) was never the problem — it's already aggregated;
only the per-student session-by-session listing scales with total session count.

**The fix.** The per-student "Details" table is now opt-in and filterable, not unconditional:

- `detail_status_ids` (`Many2many` on `ems.attendance_status`) — which statuses appear in the per-student
  "Details" table. Defaults to absence-category statuses only (`_default_detail_status_ids()`:
  `search([('category', '=', 'absence')])`), so by default the table only lists what's actually worth
  reading (misses, justified misses) instead of every "Attended" session.
- `include_strikes` (`Boolean`, default `True`) — whether the new per-student "Strikes" table (a separate
  small table, not routed through `attendance_template_details_table`/`report_eval`) is included at all.
- `detail_status_warning` (`Boolean`, `compute='_compute_detail_status_warning'`,
  `@api.depends('detail_status_ids')`) is `True` whenever the current selection isn't a subset of the
  default absence-only set (i.e. the user added something beyond the default), `False` otherwise (including
  when narrowing, e.g. down to just "Miss"). The view (`subject_wizard.xml`) renders it as an inline
  `<div class="alert alert-warning" invisible="not detail_status_warning">` on the form itself, not a
  blocking dialog — an onchange-returned `{'warning': {...}}` dict was the first approach, but was changed
  to this compute + inline-`alert` pattern (matching `views/community/working_schedules/import_wizard.xml`'s
  `blocking_error_message`/`email_mismatch_warning` fields) once a modal was found to be too disruptive for
  what's just a heads-up, not a blocking condition — the user can still submit the form either way.
- `EmsAttendanceReportSubject._get_report_values()` computes `detail_entries`/`detail_strikes` dicts
  (keyed by student) alongside the existing `lines` dict: `detail_entries[student]` is
  `grp_by_student[student]` filtered to `entry.status_id.id in detail_status_ids`; `detail_strikes[student]`
  is `ems.strike.search([('attendance_session_line_id', 'in', [that student's entry ids])])` when
  `include_strikes` is set, otherwise an empty recordset. Both are computed off `grp_by_student` — which
  still aggregates *every* entry for the "Summary" percentages regardless of `detail_status_ids` — so
  narrowing the detail table never affects the summary numbers above it.
- In `reports/attendance/subject.xml`, both the "Details" and the new "Strikes" subsection are wrapped in
  `<t t-if="detail_entries[student]">` / `<t t-if="detail_strikes[student]">` respectively, so a student
  with nothing to show in either gets neither heading.

**Gotcha hit while building the "Strikes" table**: `<td t-field="strike.date"/>` (and siblings) raised
`QWebException: Error when compiling xml template` / `AssertionError: QWeb widgets do not work correctly on
'td' elements` at render time — only caught by the browser tour (a clean `./upgrade.sh` and passing
`TransactionCase` tests don't render any QWeb, so neither catches this). QWeb widgets (`t-field`, which
picks a widget by field type) cannot be applied directly to `<td>`/`<tr>`/table-structural elements; the fix
is wrapping each field in a `<span t-field="...">` inside the `<td>` instead of putting `t-field` on the
`<td>` itself — the pattern already implicit in the rest of this report via `t-esc`, which has no such
restriction (that's why the older `attendance_template_details_table`/`report_eval` tables never hit this:
they use `t-esc`, not `t-field`, on the `<td>`).

**Also note**: the header/row column labels used by `attendance_template_details_table` (e.g. `'Date'`,
`'Teacher'` in the `header`/`rows` Python list literals set via `t-set ... t-value="[...]"`) are plain
Python string literals inside a QWeb expression attribute, not XML text nodes — Odoo's translation
extractor only picks up genuine static text content, so those never got translation `#:` references and
render in English regardless of language (a pre-existing gap, not introduced here). The new "Strikes" table
was written with literal `<th>Date</th>`-style static text instead specifically so it *would* be
extracted/translatable.

### Report robustness: student-less lines and page-break-inside

Two independent PDF-rendering issues fixed together after a "broken row" report on subject 0485 (groups
DAM1A + DAW1A):

- **Phantom blank-name row (the actual cause).** `ems.attendance_session_line.student_id` is a plain
  `Many2one` with no explicit `ondelete`, so it defaults to `ondelete='set null'`: when a student partner
  is *hard-deleted* (not archived), that student's session lines survive with `student_id = NULL`. In the
  by-subject report, `grp_by_student` keys on `entry.student_id`, so all such orphans collapse under a
  single **empty `res.partner()` recordset** key and render as one extra row/section with a blank name —
  visually a "broken" row wedged between the real students (in the reported case, right after the student
  whose lines happened to precede the orphans by id). Fixed at the source: the by-group and by-subject
  wizards' `print()` now filter `('student_id', '!=', False)` when collecting `status_ids`, so orphan lines
  never enter the report at all (they also no longer skew the subject's overall totals). The by-student
  wizard was already immune — it filters `('student_id', '=', self.student_id.id)`, which NULL never
  matches. Diagnosed by rendering the report to **HTML** (`_render_qweb_html`, no wkhtmltopdf, so no memory
  cost) and dumping the row order: the grouped student list contained an `id=False` entry. The two orphan
  lines themselves (session 38, from two students deleted from the DB) are left in place — the report is now
  robust to them regardless; deleting orphan data is a separate, centre-owned decision.
- **Row splitting across page boundaries (separate hardening).** Every per-row `<tr>` in the report tables
  (`sumary_table.xml`, `details_table.xml`, and the subject/group per-line tables + the new Strikes table)
  now carries `style="page-break-inside: avoid;"` so a single row isn't split top/bottom across two pages
  in a multi-page table. This was the initial hypothesis for the "broken row" before the phantom-row cause
  was found; kept because it's a genuine, low-risk improvement for any report table that spans pages.

### Unification: one wizard for all 3 variants

The 3 wizards (`ems.attendance_report_{group,student,subject}_wizard`) were near-identical — same dates,
same `default_get`/current-teacher/print scaffolding — differing only in the selection field, its
`allowed_*` scoping, the date-filling onchange, and which report template `print()` dispatched to. They were
merged into a single `ems.attendance_report_wizard` reached from **one** cog-menu entry, with the user
picking the variant via a `report_type` radio inside the form (chosen over keeping 3 preset entries).

- **Model.** One `report_type` `Selection`; the union of selection fields (`group_id` / `student_id` /
  `subject_id` / `group_ids`), each shown/required in the view by `report_type`. The 3 old per-variant
  `allowed_*` computes collapsed into one `_compute_allowed_ids` (`@api.depends_context('uid')` +
  `@api.depends('report_type', 'subject_id')`): `allowed_group_ids` means "the teacher's groups" for the
  by-group variant but "groups teaching the chosen subject" for by-subject — same field, branch on
  `report_type`. The 3 tutor fields collapsed into one computed `tutor_ids` (Many2many, so it holds one
  tutor for group/student and several for subject). `detail_status_ids` / `include_strikes` /
  `detail_status_warning` / `from_date` / `to_date` are now shared by all 3 variants (previously the
  detail/strikes controls existed only on the by-subject wizard). `print()` branches on `report_type` to
  build `status_ids` and pick the report `ir.actions.report` ref.
- **Report data.** The 3 `AbstractModel`s stayed (one per template/action, so grouping/layout stay
  explicit) but now share `_build_report_values(env, docids, data, group_key)` — the only difference is the
  `group_key` lambda. All 3 now produce `detail_entries`/`detail_strikes`, so the opt-in Details/Strikes
  sections render uniformly across variants.
- **Templates.** The per-dimension "Summary + (filtered) Details + Strikes" block was extracted to a shared
  `ems.attendance_template_detail_section` (`reports/attendance/templates/detail_section.xml`), `t-call`ed
  by all 3 report templates (the caller sets `section_name` / `section_data` / `section_detail_entries` /
  `section_strikes`). The by-group and by-student reports gained this per-subject section (they previously
  had none / an unfiltered one); the by-subject report's hand-written per-student block was replaced by the
  same `t-call`. Extracting it also fixed a latent bug in the old by-subject template, where each student's
  "Summary" table re-used the whole-subject `data` (the per-row `data` was never re-`t-set`), so every
  student showed the subject-wide numbers.
- **XML-ID churn / migration.** No migration script was needed: the removed records are all module-owned
  metadata that Odoo recreates/cleans up on `-u` — the 3 wizard `TransientModel`s (no persisted data), their
  3 views, and their 3 `act_window` actions. The **render side is unchanged** on purpose (the 3
  `ir.actions.report` + 3 report `AbstractModel`s + `report_name`s keep their XML IDs), so nothing that a
  saved report attachment or external reference could point at was renamed. `security/ir.model.access.csv`'s
  3×3 rows became 3 rows for the one model. The date-filling onchange also stopped calling
  `sessions.search([], ...)` (which ignored the recordset and searched *all* sessions globally) — From/To
  now reflect the actual filtered selection's range.

---

## Attendance reports (pivot/graph)

`action_attendance_report_analysis` (named "Attendance reports") opens `ems.attendance_session_line`
directly, `view_mode="pivot,graph"` — pivot is the default (first in the list), no list view. Pivot/graph/
search views live in `views/attendance/attendance_reports/analysis_views.xml`. Reuses the model's existing
`ir.model.access.csv` rows (teacher/secretary/admin already have read) — deliberately no new `ir.rule`
scoping it more tightly than the PDF wizards' underlying data already is; see the security note above.

- **Pivot** (default view): rows = `subject_id` → `student_id` (nested — subject outer, student inner, so
  a teacher's own students group naturally by subject), no columns, default measures `absence_rate` +
  `strike_count` + `__count` (set both in the pivot arch's `type="measure"` fields and in
  `action_attendance_reports_open`'s `context['pivot_measures']`, see below — the arch is the fallback for
  any entry path that bypasses the server action). `strike_count` (`ems.attendance_session_line.strike_ids`
  count) needed `store=True` added — a non-stored computed field cannot be aggregated by `read_group` at
  all, so it couldn't be used as a measure before. The pivot always renders collapsed to a single "Total"
  row on load — there is no context key or arch attribute that pre-expands row groups
  (`expandedRowGroupBys` starts `[]` and is purely client interaction state, confirmed against
  `web/static/src/views/pivot/pivot_model.js`); reaching the fully drilled-down subject/student view takes
  2 clicks on the pivot's own "Expand all" button — a deliberate choice over adding custom auto-expand JS.
- **Graph**: `<field name="subject_id"/>` (default groupBy/x-axis) + `<field name="absence_rate"
  type="measure"/>` + `<field name="strike_count" type="measure"/>`. Per the `GraphArchParser`
  (`web/static/src/views/graph/graph_arch_parser.js`): a `<field>` without `type="measure"` becomes the
  default groupBy if its type is groupable; each `<field type="measure">` becomes a *selectable* measure
  (needs `aggregator` to qualify — `absence_rate`'s is `avg`, `strike_count`'s is the Integer default
  `sum`), but **unlike pivot, the graph view can only display one measure at a time** — confirmed against
  `web/static/src/views/graph/graph_model.js`/`graph_renderer.js`: `metaData.measure` is singular
  throughout the whole data-fetch/render pipeline, and `onMeasureSelected` *replaces* it rather than
  toggling a set. The "Measures" dropdown (`web.ReportViewMeasures`, same component pivot uses) lets the
  user switch between "Absence rate" and "Strike count" with one click, each rendering its own bar chart —
  there is no built-in way to plot both as separate bar series on the same chart; that would need a custom
  chart component instead of the stock `<graph>` view.
- **Menu → role-scoped entry point**: `menu_attendance_reports` ("Reports") no longer points at the
  act_window directly — it points at `action_attendance_reports_open`, an `ir.actions.server` (`state=
  "code"`, same style as `views/academic_management/enrollment/list_tutor.xml`'s
  `action_student_group_enrollment`). Its inline code reads `action_attendance_report_analysis` via
  `env.ref(...).sudo().read()[0]`, always sets `context['pivot_measures'] = ['absence_rate', 'strike_count',
  '__count']` and `context['graph_measure'] = 'absence_rate'` (the latter is what pins the graph's default
  to "Absence rate" regardless of arch field order — `graph_measure` is read before the arch's own default,
  see `graph_model.js:181`). "Count" is available as a pivot measure alongside the other two — sample size
  matters when reading a percentage. The server action also adds a default `domain` scoping to the current
  user's own teaching
  (`[('template_teacher_ids.user_id', '=', env.uid)]`) **unless** they have `ems.group_head_of_studies`,
  `ems.group_secretary` or `ems.group_secretary_admin` — `group_head_of_studies` alone covers head of
  studies/deputy/director/academic admin too, since each implies the one below it
  (`security/groups.xml`). This is UX scoping, not a security boundary (same distinction as the wizard
  dropdowns above): an `ir.actions.act_window.domain` is baked silently into every search from *this
  specific menu entry* — unlike a `search_default_*` filter, it renders no removable facet chip, so a
  teacher can't broaden it from this screen's search bar. `ir.rule` still grants every teacher unrestricted
  read underneath, so the data remains reachable through any other path that doesn't carry this domain
  (e.g. a different view/export) — this menu entry just never offers one.
- **3 PDF wizards, reachable from the ⚙ Actions (cog) menu**: `static/src/js/backend/
  attendance_report_analysis_cog_menu.js` registers 3 `cogMenu` registry entries (same building blocks as
  `import_gedac_cog_menu.js` — a small `Component` per entry). `isDisplayed` matches on
  `env.searchModel.resModel === "ems.attendance_session_line"` and `env.config.viewType` being `pivot` or
  `graph` — **not** on `env.config.actionId` against a resolved menu `actionID` (the pattern
  `import_gedac_cog_menu.js` uses): that comparison would break here, because the menu's *configured*
  action is now the server action above, while `env.config.actionId` once the pivot is showing is the
  *act_window*'s id after the server action's redirect — the two ids never match. Matching by `resModel` +
  `viewType` sidesteps the mismatch entirely, and is precise enough since no other screen in this module
  uses this model. Odoo's generic `CogMenu` component (`@web/search/cog_menu/cog_menu`, **not**
  `ActionMenus`, which is list-view-only) is wired into both `PivotController` and `GraphController` — so
  this works on both views. Each item calls `this.action.doAction("ems.action_attendance_report_<x>_wizard")`.

---

## Views

| View | File |
|---|---|
| Unified PDF wizard form (`report_type` selector) | `views/attendance/attendance_reports/wizard.xml` |
| Analysis pivot/graph/search | `views/attendance/attendance_reports/analysis_views.xml` |
| Actions + `Attendance → Reports` menu + `action_attendance_reports_open` server action | `views/attendance/attendance_reports/menu.xml` |
| PDF templates | `reports/attendance/{group,student,subject,session}.xml` + `reports/attendance/templates/{sumary_table,details_table,detail_section}.xml` |
| ⚙ Actions cog menu (single PDF shortcut) | `static/src/js/backend/attendance_report_analysis_cog_menu.js` + `static/src/xml/backend/attendance_report_analysis_cog_menu.xml` |

## Access control

| Role | PDF wizard (create/read on `ems.attendance_report_wizard`) | Analysis screen (read on `ems.attendance_session_line`) |
|---|:---:|:---:|
| Administrator / Director / Head of Studies (+ deputy) | ✓ | ✓ (all data, no default domain) |
| Secretary (+ admin) | read-only | ✓ (all data, no default domain) |
| Teacher / Tutor / Department Chief | ✓ (dropdowns scoped to own teaching, see bug fixes above) | ✓ (defaults to own teaching via `action_attendance_reports_open`; removable, not a hard restriction — see above) |

## Testing

- `tests/test_attendance_reports.py` (`TransactionCase`): admin-vs-teacher scoping of `allowed_*` per
  `report_type` (including the bug fixes), `group_ids` prefill for the by-subject variant, `tutor_ids`
  following the type, `print()` dispatching to the right report per type + skipping student-less orphan
  lines, the stored related fields, `absence_rate`, `strike_count`'s `store=True` (aggregatable via
  `read_group`), and `action_attendance_reports_open`'s role-based domain (`.run()` `with_user(...)` for a
  plain teacher vs. an academic admin). Also: `detail_status_ids`'s default (absence-category only),
  `detail_status_warning` computing `False`/`True`, and `_get_report_values` producing correctly filtered
  `detail_entries`/`detail_strikes` for **all 3** report data models (by-subject grouped by student,
  by-group/by-student grouped by subject).
- `tests/test_attendance_reports_tour.py` + `static/tests/tours/attendance_reports_tour.js` (`HttpCase`):
  one wizard tour that switches through all 3 `report_type`s on a single open form (each variant's selector
  shows, its onchange fills tutor/dates, the by-subject prefills `group_ids`), exercises the shared Detail
  statuses / Include strikes defaults + the inline size-warning banner (absent within the default, appears
  after adding "Attended"), and prints once at the end (printing returns a report download that closes the
  dialog, so the single print comes last); plus the analysis-screen tour (pivot default, 2× Expand-all
  drilling subject → student, graph + Measures switch, and the single ⚙ cog entry opening the unified
  wizard — the only coverage of the custom `cogMenu` JS). Both `start_tour()` calls use `step_delay=300`
  (see the flakiness note above). All 3 variants' PDF *data* (QWeb HTML) render was additionally verified
  out-of-band via `_render_qweb_html` (no wkhtmltopdf), which is what catches template crashes like the
  `<td t-field=...>` one — a `TransactionCase`/clean `upgrade.sh` renders no QWeb.

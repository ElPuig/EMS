# Technical Reference: Attendance reports

## Overview

Three printable PDF reports over `ems.attendance_session_line` — by group, by student, by subject — plus a
self-service **Attendance reports** pivot/graph screen. **Attendance → Reports** opens the pivot/graph
screen directly (pivot by default); the 3 PDF wizards are reachable from its header's ⚙ Actions menu, not
from a separate menu entry.

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
(new stored fields on `ems.attendance_session_line`), `views/attendance/attendance_reports/*.xml`,
`reports/attendance/{group,student,subject}.xml` + `reports/attendance/templates/*.xml`,
`static/src/js/backend/attendance_report_analysis_cog_menu.js` +
`static/src/xml/backend/attendance_report_analysis_cog_menu.xml`.

---

## Data model

```mermaid
erDiagram
    ems_attendance_session_header ||--o{ ems_attendance_session_line : "attendance_session_id"
    ems_attendance_session_line }o--|| ems_attendance_status : "status_id"
    ems_attendance_session_line }o--o| res_partner : "student_id"
    ems_attendance_report_group_wizard ..> ems_attendance_session_line : "print() -> status_ids"
    ems_attendance_report_student_wizard ..> ems_attendance_session_line : "print() -> status_ids"
    ems_attendance_report_subject_wizard ..> ems_attendance_session_line : "print() -> status_ids"
```

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

| Wizard | Dropdown filter (`allowed_*_ids`, onchange) | `print()` |
|---|---|---|
| `..._group_wizard` | `env['ems.teaching'].search([('group_id.study_id', '=', study_id), ('teacher_id', '=', current_teacher.id)]).mapped('group_id')` | `env['ems.attendance_session_line'].search([('attendance_session_id', 'in', session_ids)])` |
| `..._student_wizard` | `env['ems.enrollment'].search([('group_id', '=', group_id), ('subject_id', 'in', taught_subject_ids)]).mapped('student_id')` | `search([('student_id', '=', ...), ('attendance_session_id.date', '>=', from), ('attendance_session_id.date', '<=', to)])` (dot-notation domain, no manual join) |
| `..._subject_wizard` | `env['ems.teaching'].search([('group_id', '=', group_id), ('teacher_id', '=', current_teacher.id)]).mapped('subject_id')` | same pattern as group's |

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
| 3 PDF wizard forms | `views/attendance/attendance_reports/{group,student,subject}_wizard.xml` |
| Analysis pivot/graph/search | `views/attendance/attendance_reports/analysis_views.xml` |
| Actions + `Attendance → Reports` menu + `action_attendance_reports_open` server action | `views/attendance/attendance_reports/menu.xml` |
| PDF templates | `reports/attendance/{group,student,subject,session}.xml` + `reports/attendance/templates/{sumary,details}_table.xml` |
| ⚙ Actions cog menu (3 PDF shortcuts) | `static/src/js/backend/attendance_report_analysis_cog_menu.js` + `static/src/xml/backend/attendance_report_analysis_cog_menu.xml` |

## Access control

| Role | PDF wizards (create/read on the `TransientModel`) | Analysis screen (read on `ems.attendance_session_line`) |
|---|:---:|:---:|
| Administrator / Director / Head of Studies (+ deputy) | ✓ | ✓ (all data, no default domain) |
| Secretary (+ admin) | read-only | ✓ (all data, no default domain) |
| Teacher / Tutor / Department Chief | ✓ (dropdowns scoped to own teaching, see bug fixes above) | ✓ (defaults to own teaching via `action_attendance_reports_open`; removable, not a hard restriction — see above) |

## Testing

- `tests/test_attendance_reports.py` (`TransactionCase`): admin-vs-teacher scoping for all 3 `allowed_*`
  computes (including both bug fixes), each wizard's `print()`, the stored related fields, `absence_rate`,
  `strike_count`'s new `store=True` (aggregatable via `read_group`), and `action_attendance_reports_open`'s
  role-based domain (`.run()` `with_user(...)` for a plain teacher vs. an academic admin).
- `tests/test_attendance_reports_tour.py` + `static/tests/tours/attendance_reports_tour.js` (`HttpCase`):
  each of the 3 wizard forms end-to-end (cascading level → study → group selection, Print); the analysis
  screen entered through the server action, pivot rendering by default, 2 clicks on "Expand all" actually
  drilling subject → student, graph on switch, switching the graph's measure from "Absence rate" to
  "Strike count" via the Measures dropdown and confirming it still renders; opening the ⚙ Actions cog menu
  and using one of the 3 PDF shortcuts to confirm it actually opens the corresponding wizard (this is the
  only coverage of the custom `cogMenu` JS — nothing server-side exercises it).

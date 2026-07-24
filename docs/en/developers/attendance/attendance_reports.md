# Technical Reference: Attendance reports

## Overview

Three printable PDF reports over `ems.attendance_session_line` — by group, by student, by subject — plus a
self-service "Attendance analysis" list/pivot/graph screen. All four are reachable from **Attendance →
Reports**.

**Trigger for this change:** the 3 PDF wizards (`ems.attendance_report_{group,student,subject}_wizard`)
used raw `cr.execute()` SQL against physical table/column names to fetch report data and to filter their
dropdowns. This broke silently on model renames (it already happened once, during the `status` →
`status_id` migration — see [ems.attendance_status](attendance_status.md)), and one wizard built its query
via unparameterized string interpolation. All SQL was replaced with ORM calls, and a native pivot/graph
screen was added so staff can explore data themselves instead of being limited to the 3 fixed PDF layouts.

**Module files:** `models/attendance/attendance_reports.py`, `models/attendance/attendance_session.py`
(new stored fields on `ems.attendance_session_line`), `views/attendance/attendance_reports/*.xml`,
`reports/attendance/{group,student,subject}.xml` + `reports/attendance/templates/*.xml`.

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

## Attendance analysis (pivot/graph)

`action_attendance_report_analysis` opens `ems.attendance_session_line` directly (`list,pivot,graph`), no
wizard step. List/pivot/graph/search views live in `views/attendance/attendance_reports/analysis_views.xml`.
Reuses the model's existing `ir.model.access.csv` rows (teacher/secretary/admin already have read) —
deliberately no new `ir.rule` scoping it more tightly than the PDF wizards' underlying data already is; see
the security note above.

The list view's `default_order="create_date desc"` (rather than a `date`-based order) is intentional: with
years of historical rows, sorting only by `date` can still tie broadly among rows sharing "today", so a
freshly created row isn't guaranteed to surface on the first page — `create_date` has no ties.

---

## Views

| View | File |
|---|---|
| 3 PDF wizard forms | `views/attendance/attendance_reports/{group,student,subject}_wizard.xml` |
| Analysis list/pivot/graph/search | `views/attendance/attendance_reports/analysis_views.xml` |
| Actions + `Attendance → Reports` menu | `views/attendance/attendance_reports/menu.xml` |
| PDF templates | `reports/attendance/{group,student,subject,session}.xml` + `reports/attendance/templates/{sumary,details}_table.xml` |

## Access control

| Role | PDF wizards (create/read on the `TransientModel`) | Analysis screen (read on `ems.attendance_session_line`) |
|---|:---:|:---:|
| Administrator | ✓ | ✓ (all data) |
| Secretary | read-only | ✓ (all data) |
| Teacher | ✓ (dropdowns scoped to own teaching, see bug fixes above) | ✓ (all data — see the `ir.rule` note above) |

## Testing

- `tests/test_attendance_reports.py` (`TransactionCase`): admin-vs-teacher scoping for all 3 `allowed_*`
  computes (including both bug fixes), each wizard's `print()`, and the new stored related fields.
- `tests/test_attendance_reports_tour.py` + `static/tests/tours/attendance_reports_tour.js` (`HttpCase`):
  each of the 3 wizard forms end-to-end (cascading level → study → group selection, Print), and the
  analysis screen switching between list/pivot/graph.

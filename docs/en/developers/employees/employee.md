# Technical Reference: `hr.employee` (EMS extension)

## Overview

`models/employees/employee.py` extends `hr.employee.base` (abstract, shared with `hr.employee.public`) and `hr.employee` themselves with everything EMS needs: employee type (teacher/ASP), roles, tutorships, department leadership, a personal weekly schedule, and photo-visibility rules. It is one of the largest, most mature files in the module — most of its behaviour already has dedicated tests and docs from earlier work; this doc is primarily a **map** tying those together, plus coverage for the pieces that were still gaps before this DTON pass.

**Module file:** `models/employees/employee.py` — two classes: `ems_employee_base` (`_inherit = ["hr.employee.base"]`, shared with the lighter `hr.employee.public`) and `ems_employee` (`_inherit = ["hr.employee"]`, the full model).

---

## Already documented elsewhere (cross-links, not duplicated here)

| Area | Fields/methods | Doc |
|------|-----------------|-----|
| Role → security group sync | `role_ids`, `_onchange_role_ids`, `update_*_role()`, `_sync_security_groups()` | [Academic role hierarchy](role_hierarchy.md) |
| `parent_id` cascade (Department Chief / Seminar Chief / Director) | `_compute_parent_id` | [Department cascade](department.md) |
| Personal calendar lifecycle | `create()`/`write()`/`unlink()`'s `resource_calendar_id` handling, `_personal_calendar_name()` | [Working schedules](working_schedule.md) |
| Weekly schedule derived breaks | `_get_derived_break_entries`, `get_derived_break_attendance_data` | [Working schedules](working_schedule.md) |
| Profile picture sync | `write_photo()`, `write()`'s photo guard | [Photo visibility](photo_visibility.md) |
| Google Workspace / EMS user creation | `action_create_google_account`, `action_create_ems_user`, OAuth pre-link | [Google Workspace staff integration](google_workspace_staff.md) |

Each of these areas already has thorough `TransactionCase` coverage (`test_employee_role_group_sync.py`, `test_employee_schedule_lifecycle.py`, `test_employee_photo_visibility.py`, `test_employee_ems_user.py`, `test_working_schedule.py`) — 60+ test methods between them. This DTON pass didn't need to add to those; it filled the remaining gaps below instead.

---

## Gaps filled in this DTON pass

### `read_only` — fixed a real bug: `compute_sudo` was silently defeating its own security check

```python
read_only = fields.Boolean(compute="_compute_read_only", compute_sudo=True, store=False)
```

Intended to mark "this user cannot edit this record" so a view can gate the whole form on it (per the field's own comment) — but it has **zero current view/JS consumers** anywhere in the module (confirmed by a full-codebase search). It was still worth fixing rather than deleting: it's cheap to get right, and a future consumer wiring it up would otherwise inherit a broken field silently.

The bug: `compute_sudo=True` runs the *entire compute* — including `self.check_access_rights('write', ...)` — as superuser, so the write-access check always saw full rights and `read_only` was always `False`, for every user, unconditionally. Fixed by re-checking against a recordset explicitly bound back to the real calling user (`self.env.user` itself is unaffected by `compute_sudo`, so `self.with_user(self.env.user).check_access_rights(...)` restores the real per-user answer):

```mermaid
flowchart TD
    A[_compute_read_only runs, self is sudo'd] --> B["self.with_user(self.env.user)\n— rebind to the real caller"]
    B --> C[check_access_rights('write') on that rebound recordset]
    C --> D[read_only = NOT can_write]
```

Covered by `tests/test_employee_display_fields.py` (`test_read_only_false_for_admin` / `test_read_only_true_for_teacher`).

### `roles` / `tutorships` — display-only computed strings

```python
roles = fields.Char(compute="_compute_roles_str", store=True)
tutorships = fields.Char(compute="_compute_tutorships_str", store=True)
```

Comma-joined `role_ids`/`tutorship_ids` names, used only for display (the employee kanban card, `views/community/employee/kanban.xml`). No bug found; just untested until this pass — covered by `tests/test_employee_display_fields.py`.

### `get_report_role_lines()` — only the Director branch was tested

One display line per `role_ids` entry for the working-schedule PDF header, appending role-specific context (tutored group(s), headed department(s), etc.) for seven roles: tutor, department chief, seminar chief, HoS, DHoS, secretary, director. Before this pass, `test_company_director.py` only exercised the director branch (`test_get_report_role_lines_director_shows_company`) — the other six were logic that had never actually run in a test. Added one test per remaining branch to the same file (it already has the department/employee creation helpers these needed).

### `ems.group.create()` didn't sync the tutor role — fixed 2026-07-27

Found while writing the `roles`/`tutorships` tests: creating an `ems.group` with `tutor_id` set **at creation time** did not add `ems.role_tutor` to the employee — only a later `write({'tutor_id': ...})` on an *existing* group did (`ems.group.write()` explicitly called `update_tutor_role()`/`_sync_security_groups()`; `create()` did not). Initially left for `ems.group`'s own DTON pass to avoid a drive-by change to a model that hadn't had its D/T/O/N cycle yet — but per the project's own DTON trigger rule (apply Testing at minimum when a change is requested to an un-DTON'd model, rather than deferring), the user asked for it to be fixed immediately once the gap was confirmed. Both `create()` and `write()` now share a `_sync_tutor_role()` helper (`models/contacts/group.py`); full D/O/N for the rest of that model — it doesn't have its own dev doc yet — still waits for its own DTON phase.

### `archived_reason_label` / `archived_reason_color` — added 2026-08-01

Feed the shared `ems_archived_reason_ribbon` field widget (`static/src/js/backend/
archived_reason_ribbon_field.js`, also used by `res.partner` — see [`contact.md`](../contacts/
contact.md)) on both `views/community/employee/{form,kanban}.xml`. Unlike `res.partner`'s
equivalent (a real compute, since only 3 of 6 `contact_type` values are ribbon-worthy), these
are **plain one-line `related=` fields** —

```python
archived_reason_label = fields.Char(related="departure_reason_id.name",
    groups="hr.group_hr_user,ems.group_teacher")
archived_reason_color = fields.Char(related="departure_reason_id.color",
    groups="hr.group_hr_user,ems.group_teacher")
```

— because *every* `hr.departure.reason` is ribbon-worthy here: there's no subset to filter down
to the way `contact_type` needs. `color` (`models/employees/departure_reason.py`, `_inherit =
["hr.departure.reason", "ems.hex_color_mixin"]`) is a new EMS addition to the native model, using
the same hex color-picker widget already established for `ems.attendance_status`/`ems.role`
(`widget="color" class="ems_color_swatch"`, added to `hr.departure.reason`'s own native list/form
via `views/community/employee/departure_reason.xml`).

**`groups=` matters here in a way it doesn't for `res.partner`**: the native
`departure_reason_id` field is itself restricted to `hr.group_hr_user` (`hr/models/
hr_employee.py`), and Odoo's own view-loading validation (`ir_ui_view.py`) raises an "Access
Rights Inconsistency" warning if a widget/field references a group-restricted field in its
`invisible=` condition without matching that same restriction — confirmed empirically
(2026-08-01: the warning appeared in `./upgrade.sh`'s log the first time these fields were added
without matching `groups=` on the ribbon elements themselves). Fixed by mirroring the exact
`groups="hr.group_hr_user,ems.group_teacher"` pattern this file already uses elsewhere (e.g.
`employee_type`, `activity_ids`) on both the field and the (adjusted, not duplicated) native
"Archived" ribbon.

**The native `hr.view_employee_form` already ships its own generic "Archived" ribbon**
(`hr_employee_views.xml`, `invisible="active"`) — this was missed on a first pass (assumed no
ribbon existed there, by analogy with the kanban, which genuinely has none), which would have
stacked two "Archived" ribbons on an archived employee with no departure reason set. Fixed by
adjusting the native ribbon's `invisible` condition in place (`invisible="active or
pending_identification or archived_reason_label"`) via `<xpath expr="//widget[@name='web_ribbon']"
position="attributes">`, the same "adjust, don't duplicate" approach `res.partner`'s form already
uses — always re-check the *native* base view for an existing ribbon before adding a new one,
not just this addon's own inherited views.

---

## Views

| View | File | Notes |
|------|------|-------|
| Form | `views/community/employee/form.xml` | Heavily inherits `hr.view_employee_form`; adds the Google Workspace header buttons, the Schedule tab (`schedule_grid` widget), the Teaching tab (tutorships/coordination/subjects) |
| Kanban | `views/community/employee/kanban.xml` | Renders `roles`/`tutorships` |
| List | `views/community/employee/list.xml` | — |
| Menu | `views/community/employee/menu.xml` | `action_employee_kanban`, already covered by `employee_google_workspace_tour.js`'s navigation, but that tour never opens the employee's own **form** — see the new `employee_tour.js` added in this pass for that gap |
| Settings tab extension | `views/settings/hr_employees_form.xml` | Out of scope here — extends the *Employees app's own* Settings tab, not EMS's |

---

## Access Control

Defined in `security/ir.model.access.csv` (lines 2–3).

| Role | Create | Read | Write | Delete | Group XML ID |
|------|:------:|:----:|:-----:|:------:|--------------|
| Administrator | ✓ | ✓ | ✓ | ✓ | `ems.group_academic_admin` |
| Teacher | — | ✓ | — | — | `ems.group_teacher` |

Plus Odoo's own `hr.group_hr_user`/`hr.group_hr_manager` access, unchanged by EMS. Several individual fields carry their own `groups=` restriction (e.g. `activity_*` fields limited to `hr.group_hr_user,ems.group_teacher`) rather than being gated at the model level.

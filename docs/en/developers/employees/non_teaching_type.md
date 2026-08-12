# Technical Reference: `ems.non_teaching_type`

## Overview

`ems.non_teaching_type` catalogues the kinds of working-schedule period that aren't a subject — guard duty, breaks, coordination meetings, etc. Consumed by the working-schedule grid (`resource.calendar.attendance.non_teaching`) to decide how a period counts toward the hours-summary columns.

**Module file:** `models/employees/non_teaching_type.py`

---

## Data Model

### Fields

| Field | Type | Required | Stored | Description |
|-------|------|----------|--------|-------------|
| `code` | `Char` | Yes | Yes | Unique code |
| `name` | `Char` (`translate=True`) | Yes | Yes | Display name |
| `sequence` | `Integer` (`default=10`) | No | Yes | Manual ordering |
| `is_break` | `Boolean` | No | Yes | Dropped from both hours-summary columns on the working schedule (e.g. lunch/patio break) |
| `is_fixed` | `Boolean` | No | Yes | Counted in the "Other fixed-schedule hours" column every day (e.g. guard duties) |
| `active` | `Boolean` (`default=True`) | No | Yes | Standard archive flag |

`_order = "sequence, name"`; `unique_code` SQL constraint.

---

## Access Control

Defined in `security/ir.model.access.csv` (lines 95–97).

| Role | Create | Read | Write | Delete | Group XML ID |
|------|:------:|:----:|:-----:|:------:|--------------|
| Department Chief | ✓ | ✓ | ✓ | ✓ | `ems.group_department_chief` |
| Teacher | — | ✓ | — | — | `ems.group_teacher` |
| Secretary | — | ✓ | — | — | `ems.group_secretary` |

Note the admin group here is `group_department_chief`, not `group_academic_admin` like most other configuration models in this cluster — intentional, since non-teaching types are a scheduling concept department chiefs manage directly.

---

## Integration Map

| Model | Field | Relation | Description |
|-------|-------|----------|--------------|
| `resource.calendar.attendance` | `non_teaching` | Many2one | Every non-subject schedule period references a type here |

See [Working schedules](working_schedule.md) for how `is_break`/`is_fixed` feed the hours-summary computation.

---

## Views

| View | File | Notes |
|------|------|-------|
| List | `views/employees/non_teaching_type/list.xml` | — |
| Form | `views/employees/non_teaching_type/form.xml` | — |
| Action + Menu | `views/employees/non_teaching_type/menu.xml` | — |

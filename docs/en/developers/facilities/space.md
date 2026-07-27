# Technical Reference: `ems.space`

## Overview

`ems.space` is a physical space (classroom, lab, etc.) a group, session, minute or teacher's schedule can be located in. No business logic beyond the computed `display_name` — a plain, widely-referenced lookup model.

**Module file:** `models/facilities/space.py`

---

## Data Model

### Fields

| Field | Type | Required | Stored | Description |
|-------|------|----------|--------|-------------|
| `code` | `Char` | Yes | Yes | Unique per work location (see constraint below) |
| `name` | `Char` | Yes | Yes | Display name |
| `space_type_id` | `Many2one → ems.space_type` | Yes | Yes | — |
| `work_location_id` | `Many2one → hr.work.location` | Yes | Yes | Which site/building this space belongs to |
| `display_name` | `Char` (computed) | — | No | Format: `Name (Code)` |

`_order = "name"` (added in this DTON pass). `_rec_names_search = ['name', 'code']` — the name-search box matches on both. `unique_code` SQL constraint is scoped to `(work_location_id, code)`, not `code` alone — the same code can be reused across different work locations/sites.

---

## Access Control

Defined in `security/ir.model.access.csv` (lines 22–24).

| Role | Create | Read | Write | Delete | Group XML ID |
|------|:------:|:----:|:-----:|:------:|--------------|
| Administrator | ✓ | ✓ | ✓ | ✓ | `ems.group_academic_admin` |
| Teacher | — | ✓ | — | — | `ems.group_teacher` |
| Secretary | — | ✓ | — | — | `ems.group_secretary` |

---

## Integration Map

`ems.space` is referenced (as `space_id`) by:

| Model | Required |
|-------|:--------:|
| `ems.record` | No |
| `ems.minute` | Yes |
| `ems.attendance_schedule` | Yes |
| `ems.attendance_template` | Yes |
| `ems.attendance_session_header` | Computed from the template |
| `resource.calendar.attendance` (working schedule) | Computed |
| `ems.group` | No (a group's usual classroom) |

---

## Views

| View | File |
|------|------|
| List | `views/community/space/list.xml` |
| Form | `views/community/space/form.xml` |
| Search | `views/community/space/search.xml` |
| Action + Menu | `views/community/space/menu.xml` |

---

## Data Files

| File | Purpose |
|------|---------|
| `data/custom/ems.space.csv` | Centre-specific catalog |
| `demo/facilities/space.xml` | Demo data |

# Technical Reference: `ems.space`

## Overview

`ems.space` is a physical space (classroom, lab, etc.) a group, session, minute or teacher's schedule can be located in. Its own business logic is limited to the computed `display_name` and a `write()` hook that keeps groups' public schedule PDFs in sync (see Integration Map below) — a plain, widely-referenced lookup model, extended by `models/facilities/space_schedule.py` (see [Space (classroom) occupation schedule](space_schedule.md)) with a read-only aggregated weekly occupation schedule.

**Module files:** `models/facilities/space.py` (base model), `models/facilities/space_schedule.py` (occupation schedule).

---

## Data Model

### Fields

| Field | Type | Required | Stored | Description |
|-------|------|----------|--------|-------------|
| `code` | `Char` | Yes | Yes | Unique per work location (see constraint below) |
| `name` | `Char` | Yes | Yes | Display name |
| `space_type_id` | `Many2one → ems.space_type` | Yes | Yes | Defaults to "Classroom" (`ems.space_type_classroom`) on a new record |
| `work_location_id` | `Many2one → hr.work.location` | Yes | Yes | Which site/building this space belongs to; labeled "Location" on the form. Defaults to "Main building" (`ems.work_location_main`) on a new record |
| `schedule_attendance_ids` | `Many2many → resource.calendar.attendance` (computed) | — | No | This room's aggregated weekly occupation — see [space_schedule.md](space_schedule.md) |
| `display_name` | `Char` (computed) | — | No | Format: `Name (Code)` |

`_inherit = ['mail.thread', 'mail.activity.mixin']` — chatter (messages/notes/activities/followers) on the form, no other mixin behavior. `_order = "name"`. `_rec_names_search = ['name', 'code']` — the name-search box matches on both. `unique_code` SQL constraint is scoped to `(work_location_id, code)`, not `code` alone — the same code can be reused across different work locations/sites.

`ems.space_type.name` is translatable (`translate=True`) — the seeded types (Classroom, Equipment, Laboratory, Office, Workshop) have real Catalan/Spanish translations, not just English.

`hr.work.location.name` (native Odoo `hr` module field, non-translatable by default) is made translatable too, via a plain field-redeclaration extension: `models/facilities/work_location.py` (`_inherit = 'hr.work.location'`). "Main building" (`ems.work_location_main`, `data/main/hr.work.location.csv`) has real Catalan/Spanish translations; the 3 other, vestigial `hr.work.location` seed rows shipped by core Odoo itself (Home/Office/Other) are not used by any real `ems.space` record on this box and were left untranslated.

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

The form is two rows of two columns each (code/name, then type/location — each "column" a
label+field pair via nested `<group>`s), a "Schedule" tab (see
[space_schedule.md](space_schedule.md)), and a chatter.

---

## Data Files

| File | Purpose |
|------|---------|
| `data/custom/ems.space.csv` | Centre-specific catalog |
| `demo/facilities/space.xml` | Demo data |

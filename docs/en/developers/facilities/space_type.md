# Technical Reference: `ems.space_type`

## Overview

`ems.space_type` catalogues the kinds of physical space a centre has (classroom, laboratory, workshop, etc.). No computed fields, no constraints, no business logic — a plain lookup table consumed by `ems.space.space_type_id`.

**Module file:** `models/facilities/space_type.py`

The model had a stale `# TODO: config page in facilities to manage this model` comment (removed in this DTON pass) — it already has a full list/form/menu (`views/community/space_type/`), registered in the manifest and reachable from Community → Configuration; the TODO predates that and no longer applies.

---

## Data Model

### Fields

| Field | Type | Required | Stored | Description |
|-------|------|----------|--------|-------------|
| `name` | `Char` | Yes | Yes | Display name (e.g. "Classroom", "Laboratory") |

`_order = "name"` (added in this DTON pass).

---

## Access Control

Defined in `security/ir.model.access.csv` (lines 26–28).

| Role | Create | Read | Write | Delete | Group XML ID |
|------|:------:|:----:|:-----:|:------:|--------------|
| Administrator | ✓ | ✓ | ✓ | ✓ | `ems.group_academic_admin` |
| Teacher | — | ✓ | — | — | `ems.group_teacher` |
| Secretary | — | ✓ | — | — | `ems.group_secretary` |

---

## Integration Map

| Model | Field | Relation |
|-------|-------|----------|
| `ems.space` | `space_type_id` | Many2one (required) |

---

## Views

| View | File |
|------|------|
| List | `views/community/space_type/list.xml` |
| Form | `views/community/space_type/form.xml` |
| Action + Menu | `views/community/space_type/menu.xml` |

---

## Data Files

| File | Purpose |
|------|---------|
| `data/main/ems.space_type.csv` | Production catalog |
| `demo/facilities/space_type.xml` | Demo data |

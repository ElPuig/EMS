# Technical Reference: `ems.study`

## Overview

`ems.study` is a configuration model in the EMS curriculum hierarchy, one level below `ems.level`. It represents a concrete study programme (e.g., DAM, DAW, ASIX) offered under a given educational level, and links it to the subjects that make it up.

**Module file:** `models/curriculum/study.py`

---

## Data Model

### Fields

| Field | Type | Required | Stored | Description |
|-------|------|----------|--------|-------------|
| `code` | `Char` | Yes | Yes | Official code, unique (e.g., `CFGS_ICB0`) |
| `acronym` | `Char` | Yes | Yes | Short code (e.g., `DAM`) |
| `name` | `Char` | Yes | Yes | Full descriptive name |
| `date` | `Date` | Yes | Yes | Release/curriculum publication date |
| `deprecated` | `Boolean` | Yes | Yes | Marks a study as no longer offered, without deleting historical data |
| `level_id` | `Many2one → ems.level` | No | Yes | The level this study belongs to |
| `subject_ids` | `Many2many → ems.subject` | No | Yes | Subjects that make up this study |
| `follow_ids` | `One2many → ems.tracking` | No | No | Follow-up/tracking records for this study |
| `attachment_ids` | `Many2many → ir.attachment` | No | Yes | Curriculum documents (BOE/DOGC references, guidance docs) |
| `notes` | `Text` | No | Yes | Free-form administrative notes |
| `display_name` | `Char` (computed) | — | No | Format: `ACRONYM (Year): Name` |
| `uses_enrollment_flow` | `Boolean` (computed, searchable) | — | No | Whether the study has at least one active `sale.order.template` |

### Curriculum Hierarchy

```mermaid
graph TD
    L["ems.level (e.g. CFGS)"]
    S["ems.study (e.g. DAM)"]
    SU["ems.subject (e.g. Programming)"]
    G["ems.group (e.g. DAM-1)"]
    ST["Students (res.partner)"]

    L --> S
    S -->|subject_ids| SU
    S -->|study_id, via contacts/enrollment| G
    G --> ST
```

### `display_name` Computation

Triggered by `@api.depends('acronym', 'name')`. Note `date` is read but not declared as a dependency — the year only changes when a new record is created with a different `date`, so this is intentional (matches the model's original design; not a bug worth fixing without a behaviour change).

```mermaid
flowchart LR
    A["acronym"] --> D["display_name = 'acronym (year): name'"]
    B["name"] --> D
    C["date (year, or current year if unset)"] --> D
```

### `uses_enrollment_flow` Computation

Single source of truth for whether a study manages admissions through the matrícula (`sale.order`) flow. Derived — not a manual flag — from whether the study has at least one active [enrollment template](../enrollment/enrollment_template.md) (`sale.order.template`) pointing at it via `ems_study_id`. Consumed by the "no destination" report, the transition-status computation, and the transition wizard preview.

```mermaid
flowchart TD
    A[ems.study] --> B{Any active sale.order.template<br/>with ems_study_id = this study?}
    B -- Yes --> C[uses_enrollment_flow = True]
    B -- No --> D[uses_enrollment_flow = False]
```

---

## CRUD Operations

### Create

```mermaid
flowchart TD
    A([Admin user]) --> B[Community → Config → Curriculum → Studies]
    B --> C[Click New]
    C --> D[Fill code + acronym + name + date]
    D --> E[Save]
    E --> F{ORM / DB validation}
    F -- missing required field --> G[Error: required field constraint]
    F -- duplicate code --> H[Error: unique_code constraint]
    F -- valid --> I[(INSERT INTO ems_study)]
    I --> J([Record created])
```

### Read

```mermaid
flowchart TD
    A([Any user with read access]) --> B[Community → Config → Curriculum → Studies]
    B --> C[List view: sorted by code ASC]
    C --> D[Click record]
    D --> E[Form view: main data · administrative data · Subjects tab · Attached files tab · Notes tab]
```

### Update

```mermaid
flowchart TD
    A([Admin user]) --> B[Open study record]
    B --> C[Edit fields]
    C --> D[Save]
    D --> E{Validation}
    E -- required field cleared --> F[Error: required field constraint]
    E -- valid --> G[(UPDATE ems_study SET ...)]
    G --> H([display_name / uses_enrollment_flow recomputed])
```

### Delete

```mermaid
flowchart TD
    A([Admin user]) --> B[Select study in list]
    B --> C[Action ⚙ → Delete]
    C --> D[Confirm dialog]
    D --> E{Linked records with a hard FK<br/>e.g. ems.planning.study_id}
    E -- Yes --> F[DB integrity error: cannot delete]
    E -- No --> G[(DELETE FROM ems_study WHERE id = ...)]
    G --> H([Record removed])
```

In practice, production studies are rarely deleted — the `deprecated` flag is the intended way to retire a study while keeping its historical enrolments, groups and grades intact.

---

## Access Control

Defined in `security/ir.model.access.csv` (lines 46–48, 229).

| Role | Create | Read | Write | Delete | Group XML ID |
|------|:------:|:----:|:-----:|:------:|--------------|
| Administrator | ✓ | ✓ | ✓ | ✓ | `ems.group_academic_admin` |
| Teacher | — | ✓ | — | — | `ems.group_teacher` |
| Secretary | — | ✓ | — | — | `ems.group_secretary` |
| Portal | — | ✓ | — | — | `base.group_portal` |

No record-level rules exist for this model. Teacher/Secretary/Portal read access exists so studies can be displayed (selectors, tags, filters) in other screens — none of these roles has a dedicated "Studies" menu entry of their own.

---

## Integration Map

`ems.study` is referenced by the following models:

| Model | Field | Relation | Description |
|-------|-------|----------|--------------|
| `ems.level` | `study_ids` | One2many | Inverse of `study.level_id` |
| `ems.subject` | `study_ids` | Many2many | Subjects can belong to multiple studies |
| `ems.group` | `study_id` | Many2one | Each class group belongs to one study |
| `ems.contact` (`res.partner`) | `study_id` / `preinscription_study_id` | Many2one | Student's current and pre-registration study |
| `ems.planning` | `study_id` | Many2one (required) | Planning is scoped to a study |
| `ems.tracking` | `study_id` | Many2one | Follow-up records scoped to a study |
| `ems.enrollment` | `ems_study_id` | Many2one | Enrolment header targets a study; derives `ems_level_id` |
| `ems.authorization` / `ems.authorization.template` | `ems_study_id` / `ems_study_ids` | Many2one / Many2many | Authorization scope |
| [Enrollment template](../enrollment/enrollment_template.md) (`sale.order.template`) | `ems_study_id` | Many2one | Drives `uses_enrollment_flow` |
| `ems.attendance_template` | `study_ids` | Many2many | Attendance scheduling; can span several studies (co-teaching) |
| `ems.attendance_session_header` / `_line` | `study_ids` | Related (`store=True`) | Inherited from the attendance template |
| `ems.student.year_record` | `study_id` | Many2one | Historical academic record |
| `ems.em_grading_wizard` | `study_id` | Many2one | Work-placement grading scope |
| `ems.grade_session_state_wizard` | `study_ids` | Many2many | Bulk grade-session state changes |
| `ems.limesurvey_header` | `study_ids` | Many2many | Survey targeting by study |

---

## Views

| View | File | Notes |
|------|------|-------|
| List | `views/community/study/list.xml` | Sorted by `code` |
| Form | `views/community/study/form.xml` | Main + administrative data groups; Subjects / Attached files / Notes tabs |
| Search | `views/community/study/search.xml` | — |
| Action + Menu | `views/community/study/menu.xml` | `action_study_tree`, under Community → Configuration → Curriculum (sequence 2) |

`study_ids`/`study_id` are also rendered as `many2many_tags` on `ems.authorization.template`, `ems.enrollment.authorization`, `ems.minute` and the grading wizard forms — these are simple tag pickers, not custom widgets, so they don't require dedicated tour coverage beyond the model's own CRUD screen.

---

## Data Files

| File | Purpose |
|------|---------|
| `data/cat/ems.study.csv` | Production catalog: Catalan VET/Baccalaureate studies |
| `data/custom/ccff/ems.study.csv`, `data/custom/btx/ems.study.csv`, `data/custom/eso/ems.study.csv` | Centre-specific extensions reusing the shared `data/cat` ids (see CLAUDE.md "extending a `data/cat/` record" exception) to attach the centre's own optional subjects |

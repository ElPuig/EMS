# Technical Reference: `ems.tracking`

## Overview

`ems.tracking` is a free-form follow-up note a tutor or teacher can attach to a student — optionally scoped to a study and/or subject. No computed fields, no constraints, no business logic beyond plain CRUD.

**Module file:** `models/employees/tracking.py`

---

## Data Model

### Fields

| Field | Type | Required | Stored | Description |
|-------|------|----------|--------|-------------|
| `notes` | `Text` | No | Yes | The follow-up note itself |
| `teacher_id` | `Many2one → hr.employee` | No | Yes | Domain restricted to `employee_type = 'teacher'` |
| `student_id` | `Many2one → res.partner` | No | Yes | The student this note is about |
| `study_id` | `Many2one → ems.study` | No | Yes | Optional scope |
| `subject_id` | `Many2one → ems.subject` | No | Yes | Optional scope |

None of the relational fields are `required=True` at the model level — the form enforces what it needs contextually. `_order = "id desc"` (added in this DTON pass) shows the most recent notes first, matching how a follow-up log is actually read.

---

## Access Control

Defined in `security/ir.model.access.csv` (lines 30–32).

| Role | Create | Read | Write | Delete | Group XML ID |
|------|:------:|:----:|:-----:|:------:|--------------|
| Administrator | ✓ | ✓ | ✓ | ✓ | `ems.group_academic_admin` |
| Teacher | — | ✓ | — | — | `ems.group_teacher` |
| Secretary | — | ✓ | — | — | `ems.group_secretary` |

Note: teachers only have **read** access at the model level despite `ems.tracking` being described as something "tutors and teachers can add" — worth flagging if that turns out to be a real gap rather than intentional (e.g. tracking notes might be meant to be entered by admin/secretary on a teacher's behalf, or this access row predates the current intent). Not changed in this DTON pass — a security-scope change needs an explicit decision, not a drive-by fix.

---

## Views — none currently loaded

`views/community/tracking/{list,form,menu}.xml` all exist on disk, fully written, but **all three are commented out in `__manifest__.py`'s `data` list** (lines ~194–196). This isn't a missing-menu oversight like it first appears — the model has **no view, no action, and no menu registered in the database at all**. `action_tracking_tree` (declared in `menu.xml`) doesn't exist as a DB record; navigating to it 404s with Odoo's "Missing Action" dialog. The file also has its own `TODO: this should be the tracking info about a student` comment, suggesting the views were disabled pending a redesign (e.g. embedding on the student's contact form) rather than by accident.

Separately, `ems.study.follow_ids` (One2many, inverse of `tracking.study_id`) is declared on `ems.study` but was never placed in `views/community/study/form.xml` either, even if the tracking views were re-enabled as-is.

**Per the New feature workflow's own exemption** ("skip [the tour] only for a model with no UI surface at all") — this model currently has none, so no tour was added; a `TransactionCase` covering the model/ACL directly (`tests/test_tracking.py`) is the appropriate level of testing for its actual current state. Not fixed here: re-enabling the manifest lines and/or wiring up where this should actually live is a feature decision (matching the TODO's own note), not a retroactive DTON fix — flagged for whoever picks that up next.

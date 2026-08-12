# Technical Reference: `hr.job` (EMS extension)

## Overview

`models/employees/job.py` extends Odoo's `hr.job` with two fields: which EMS employee type the position applies to, and an optional security group to auto-grant. It has no custom methods of its own — `group_id` is consumed entirely from `hr.employee`'s side (`_sync_security_groups()`), already covered by [the role hierarchy doc](role_hierarchy.md) and `test_employee_role_group_sync.py`'s `test_assign_job_secretary_adds_group`/`test_unassign_job_secretary_removes_group`.

**Module file:** `models/employees/job.py`

---

## Data Model

### Fields

| Field | Type | Required | Stored | Description |
|-------|------|----------|--------|-------------|
| `employee_type` | `Selection` (`asp`/`teacher`) | No | Yes | Which EMS employee type this job position applies to — drives the domain on `hr.employee.job_id` (`views/community/job/form.xml` replaces the native `department_id` field with this one) |
| `group_id` | `Many2one → res.groups` | No | Yes | If set, every employee holding this job position is automatically added to this security group (see `hr.employee._sync_security_groups()`) |

---

## Access Control

Defined in `security/ir.model.access.csv` (lines 10–12).

| Role | Create | Read | Write | Delete | Group XML ID |
|------|:------:|:----:|:-----:|:------:|--------------|
| Administrator | ✓ | ✓ | ✓ | ✓ | `ems.group_academic_admin` |
| Teacher | — | ✓ | — | — | `ems.group_teacher` |
| Secretary | — | ✓ | — | — | `ems.group_secretary` |

---

## Views

| View | File | Notes |
|------|------|-------|
| Form | `views/community/job/form.xml` | Inherits `hr.view_hr_job_form`; hides recruitment/contract-type sections not used by EMS, replaces `department_id` with `employee_type` |
| Action + Menu | `views/community/job/menu.xml` | `action_job_tree`, under Community → Configuration → HR (sequence 3) |

**No browser tour for this model.** `hr.job`'s "New" quick-create form is a separate, minimal native Odoo view (just the name field, not a real `<input>` — a contenteditable-style hero title, which made it impractical to drive from a tour without disproportionate effort for a 2-field extension). Risk here is low: no custom JS widgets, the arch changes are simple attribute-level XPaths already validated by a clean `./upgrade.sh`, and the fields themselves are covered by `tests/test_job.py`. Revisit if `views/community/job/form.xml` grows more complex.

# Technical Reference: `ems.minute`

## Overview

`ems.minute` records a meeting minute — department meeting, workgroup meeting, or evaluation
meeting — with when/where/who attended and an abstract of the topic. **This is an
early-stage feature**: the model's own extensive `TODO` block (preserved verbatim in the
source) describes a much larger intended scope — configurable minute types with structured
content sections, an approval/signature workflow, PDF generation — none of which exists yet.
Today the model only captures the basic identifying fields; this doc covers what's actually
implemented, not the aspirational design in the comments.

**Module file:** `models/documentation/minute.py` (`EmsMinute`)

**Not to be confused with `ems.record`** — an earlier, abandoned attempt at this same
feature, superseded when it was renamed to `ems.minute` (git history: *"Record has been
renamed to 'minute'. Setting up forms and lists."*). `models/documentation/record.py` was
never deleted after that rename, had no views/menu/`ir.model.access.csv` rows anywhere, and
wasn't even imported by `models/documentation/__init__.py` — genuinely unreachable, not a
parallel feature. Confirmed with the developer and deleted in this same pass (2026-07-28).

---

## Fields

| Field | Type | Notes |
|-------|------|-------|
| `type` | `Selection` (department/workgroup/evaluation) | Determines which of `department_id`/`workgroup_id` the form shows (`invisible` toggles on `type`). |
| `department_id`/`workgroup_id` | `Many2one` | Only one is relevant depending on `type` — neither is `required` at the model level (view-level guidance only). |
| `assistant_ids`/`abstent_ids` | `Many2many → res.partner` | `domain="[('type','=','contact')]"` — this filters on `res.partner`'s **native** `type` field (address kind: contact/invoice/delivery/other/private), not EMS's own `contact_type` (student/family/teacher/...). In practice this barely restricts anything, since `'contact'` is the default address kind for nearly every partner in the system — worth a second look if the intent was actually "teachers/staff only," since the two same-named `type` fields on `res.partner` are an easy mix-up. Not changed in this pass (guessing the intended filter would be inventing business logic, not a normalization fix). |
| `members` | computed | A one-line summary: `"Department: {name}"` or `"Workgroup: {name}"` depending on `type`. |

---

## Two real bugs found and fixed in this pass

**1. `_compute_display_name` compared the Python builtin `type`, not the record's field.**

```python
rec.workgroup_id.name if type == "workgroup" else rec.department_id.name
```

`type` here resolved to Python's builtin `type` object (no local variable shadowing it) —
comparing it to the string `"workgroup"` is always `False` (different, unrelated objects),
so `display_name` **always** showed `department_id.name`, even for a workgroup meeting
(where `department_id` is typically blank). The near-identical `_compute_members` right
below it correctly used `rec.type` — this was an isolated typo in one of the two methods,
not a design choice. Fixed to `minute.type`. Regression test:
`test_display_name_workgroup_meeting`.

**2. `_compute_members` was missing dependencies.**

`@api.depends("type")` only — not `workgroup_id`/`department_id`. Changing which workgroup a
minute belongs to (without touching `type`) left `members` showing the *previous* group's
name, since Odoo only recomputes a field when one of its **declared** dependencies changes.
Fixed by adding both fields to the `@api.depends`. Regression test:
`test_members_recomputes_when_workgroup_changes`.

**3. `date`'s default was a frozen value, not a callable.**

`default=datetime.today()` — called immediately, once, when the field is defined (module/
registry load time), baking in a single fixed timestamp shared by *every* future record
rather than each record's actual creation time. Fixed to `default=fields.Datetime.now` (the
function itself, not called) — the established idiom already used correctly elsewhere in
this codebase (e.g. `attendance_session.py`'s own `date` field).

---

## A framework limitation worth remembering: `required=True` on x2many fields

`assistant_ids` is declared `required=True`, but Odoo **never enforces `required` for a
One2many/Many2many field at the ORM level** — only the form view blocks saving with none
selected. A direct `create()` via RPC/script/test with no assistants succeeds without error.
This is standard Odoo behavior (not specific to this model), but easy to assume otherwise;
documented here and in `test_assistant_ids_required_is_ui_only_not_orm_enforced` so it isn't
mistaken for a bug in a future pass.

## Views

| View | File |
|------|------|
| List/Form | `views/documentation/minutes/{list,form}.xml` |
| Menu | `views/documentation/minutes/menu.xml` |

## Fixed in this pass (2026-07-28)

Class renamed `minute` → `EmsMinute` (bare lowercase class name, matching neither the
snake_case nor PascalCase convention used elsewhere — now aligned with the PascalCase
standard for models with their own `_name`). Tab-indented → spaces. Loop variable `rec` →
`minute`. Field label typo `"Memebers"` → `"Members"` (reused the project's existing
"Members" `.po` block via a new `#:` reference, per the reused-label rule, rather than
duplicating a translation). The three bugs above. New `tests/test_minute.py` (8 tests) — no
coverage existed before this pass. The model's own extensive feature `TODO`s (minute types,
approval/signature workflow) are pre-existing, explicitly out-of-scope design notes, not a
DTON finding — left untouched, verbatim, in the source.

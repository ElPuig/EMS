# Technical Reference: `ems.attendance_template`

## Overview

An `ems.attendance_template` answers "who teaches what, where and for whom": one record groups a teacher-set + subject + set of groups into a weekly schedule (its `attendance_schedule_ids`, the actual weekday/start_time/end_time slots) plus the enrolled students expected to attend. Templates are the backbone that turns a raw weekly schedule (imported from an XML planner file, or edited live from a teacher's own "Schedule" tab) into what the attendance roll-call screens actually check students against.

Templates are **not created directly by an admin filling in a form** in the normal case — they are derived by `sync_from_schedule_batch()` from schedule entries, reconciling co-teaching and splitting/merging templates as needed (see "CRUD flow" below). The form/list views exist for inspecting and manually correcting the result, not as the primary entry point.

`ems.attendance_template` also carries `mail.thread`/`mail.activity.mixin` (chatter) — every archive/clone via the "Edit" button (see below) and manual identity-field edit is tracked there.

**Module files:** `models/attendance/attendance_template.py`, `views/attendance/attendance_template/`, `models/shared/hex_color_mixin.py` (color), `models/attendance/attendance_schedule.py` (the weekly slots, own fields/logic documented in [`attendance_schedule.md`](attendance_schedule.md)).

## Relations

```mermaid
erDiagram
    ems_attendance_template ||--o{ ems_attendance_schedule : "attendance_schedule_ids (weekly slots)"
    ems_attendance_template }o--o{ hr_employee : "teacher_ids"
    ems_attendance_template }o--|| ems_subject : subject_id
    ems_attendance_template }o--o{ ems_group : group_ids
    ems_attendance_template }o--|| ems_space : space_id
    ems_attendance_template }o--o{ res_partner : "student_ids (students)"
    ems_attendance_template }o--o{ ems_study : study_ids
```

`study_ids` is **not required** — a template built from a *reinforcement* `ems.group` (`group_type == 'reinforcement'`) has no study of its own and leaves it empty (see `_write_schedule_sync`). There is no `level_id` on this model anymore (removed 2026-08-05, see "Identity fields, locking..." below) — a level is always derivable from `group_ids`/`study_ids` when needed (e.g. `ems.attendance_session_header.level_id`, still on the session side, is computed straight from `group_ids[:1].level_id`).

## Data model

| Field | Type | Notes |
|-------|------|-------|
| `start_date` / `end_date` | `Date`, required | The template's active date range |
| `color` | `Char` (hex) | Free-pick display color, auto-assigned on creation — see [Free-pick color widget](../shared/color_widget.md) |
| `teacher_ids` | `Many2many → hr.employee` | Required. Domain restricted to `employee_type = 'teacher'`. More than one teacher means co-teaching. Locked (`readonly`) once `has_sessions` unless `user_is_admin` |
| `subject_id` | `Many2one → ems.subject` | Required. Domain restricted to `allowed_subject_ids`. Locked once `has_sessions` |
| `study_ids` | `Many2many → ems.study` | Optional (see above). Locked once `has_sessions` |
| `group_ids` | `Many2many → ems.group` | Required (`_check_group_ids`). Domain restricted to `study_id in study_ids`. Locked once `has_sessions` |
| `allowed_subject_ids` | `Many2many → ems.subject`, computed, non-stored | Subjects available in **every** one of `study_ids` (intersection, not union) — backs `subject_id`'s domain and `_check_subject_valid_for_all_studies` below. Empty `study_ids` means no restriction (all subjects allowed) |
| `space_id` | `Many2one → ems.space` | Required. Auto-filled from the first group's own space on `group_ids` change |
| `attendance_schedule_ids` | `One2many → ems.attendance_schedule` | The actual weekly weekday/start_time/end_time slots |
| `student_ids` | `Many2many → res.partner` | Auto-filled (`fill_students()`) from active enrollments matching `subject_id` + `group_ids` |
| `has_sessions` | `Boolean`, computed | `True` once any of this template's schedules has a real `attendance_session_ids` entry — see "Identity fields, locking..." below |
| `read_only_user` | `Boolean`, non-stored | `True` unless: admin, one of `teacher_ids`, or the record's own creator |

### `_check_subject_valid_for_all_studies`

`@api.constrains('subject_id', 'study_ids')`: rejects a `subject_id` that isn't in `allowed_subject_ids` whenever `study_ids` is non-empty — i.e. the chosen subject must actually be taught in **every** selected study, not just one of them. A reinforcement template (no `study_ids`) is never subject to this.

## Identity fields, locking, and the "Edit" button

Once a template has real attendance history (`has_sessions`), its **identity fields** —
`teacher_ids`, `subject_id`, `study_ids`, `group_ids` (template-level) and each schedule
line's `weekday`/`space_id`/`start_time`/`end_time` (line-level, see
[`attendance_schedule.md`](attendance_schedule.md)) — become readonly in the form. Editing
them in place after real sessions exist would retroactively misrepresent what those already-taken
sessions were actually about (every `ems.attendance_session_header` field mirroring them is
`related`+`store=True`, so an in-place edit would silently rewrite history — see
[`attendance_session.md`](attendance_session.md)).

Correcting a mistake (or handling a legitimate mid-year change of teacher/subject/group) is done
via **`action_new_version()`** instead of unlocking the field — surfaced in the UI as an **"Edit"**
button (`icon="fa-pencil-square-o"`, renamed from "New version" 2026-08-05 per the developer: from
the user's perspective this *is* editing a locked template, the archive+clone happening
underneath is an implementation detail the confirm dialog still spells out, not something the
button label needs to advertise):

```mermaid
flowchart TD
    A["action_new_version() on the template\n(or schedule line - see attendance_schedule.md)"] --> B["_write_or_new_version({})\n(ems.attendance_mixin, shared with the sync pipeline below)"]
    B --> C["action_archive()\n(cascades to schedule lines too, template-level)"]
    C --> D["copy({'active': True})"]
    D --> E["new_template.attendance_schedule_ids.action_unarchive()\n(copy() carries over each line's just-archived 'active')"]
    E --> F["open the new, fully editable copy\n(view_mode: form)"]
```

**`ems.attendance_mixin`** (`models/shared/attendance_mixin.py`, in both this model's and
`ems.attendance_schedule`'s `_inherit`) supplies the one shared decision behind every caller that
can change a locked field: `_write_or_new_version(vals)` writes `vals` in place if
`not self.has_sessions`, or archives `self` and returns `self.copy({'active': True, **vals})`
otherwise. `action_new_version()` is a thin wrapper calling it with `vals={}` (this button only
exists to unlock the record for a *subsequent* manual edit, not to apply a value itself) — always
taking the archive+clone branch in practice, since the view only shows the button once
`has_sessions` is already `True`. The **schedule-sync pipeline** (`_archive_stale_schedule_sync`/
`_write_schedule_sync`, see "CRUD flow" below) shares the exact same `has_sessions` predicate for
its own per-schedule-line decisions, though it can't call this method as a single atomic step —
see that section for why. Deliberately named generically (not e.g. `ems.has_sessions_lock_mixin`)
so it can hold other shared attendance-model code later too, not just this one rule.

Archiving happens **before** copying, not after — copying first would momentarily leave the
original and the identical fresh clone both active, sharing the same
teacher/room/time/subject, which `ems.attendance_schedule.check_overlap()` correctly rejects
as a double-booking. The already-taken sessions stay linked to the archived original,
permanently accurate; the clone starts with no session history (`attendance_session_ids` is
`copy=False`), so every identity field is freely editable again.

## CRUD flow

The entry points are `sync_from_schedule()` (single teacher, e.g. the employee "Schedule" tab's live editor) and `sync_from_schedule_batch()` (several teachers at once, e.g. the XML planner importer) — both funnel through the same three-stage pipeline, so a solo live edit and a multi-teacher import share identical co-teaching/conflict logic:

```mermaid
flowchart TD
    A["sync_from_schedule(teacher, entries)"] --> B["sync_from_schedule_batch([(teacher, entries)])"]
    C["XML importer: several teachers"] --> B
    B --> D["_reconcile_teacher_groups(): merge submitted entries against\nwhat's already in the DB for the same subject+group-set,\nat the exact weekday/time slot level"]
    D --> E["vacated.action_archive(): templates fully superseded, no surviving teacher"]
    D --> F["merged: (teachers, entries) pairs"]
    F --> G["_plan_schedule_sync() per pair: which existing templates\nmatch exactly (subject+groups+teacher-set), what the fresh\nentries look like grouped by subject+group-set"]
    G --> H["_archive_stale_schedule_sync() for EVERY plan first"]
    H --> I["_write_schedule_sync() for every plan: refresh survivors,\ncreate genuinely new templates (auto-assigned color)"]
```

Key behaviours, each covered by its own docstring in the code:

- **Co-teaching reconciliation** (`_reconcile_teacher_groups`) works at the exact (weekday, start_time, end_time) slot level, not at the whole-template level — a single teacher's live edit can retroactively **split** another teacher's existing template if they now land on the exact same slot, or leave it alone otherwise.
- **Archive-then-write, in two full passes across the whole batch** (`_archive_stale_schedule_sync` for every plan, then `_write_schedule_sync` for every plan) — never interleaved per-plan. Interleaving would let one plan's fresh line collide (via `ems.attendance_schedule.check_overlap()`) with another plan's still-active *stale* line that hasn't been re-synced yet, when two groups share a classroom.
- **Per-line, `has_sessions`-aware matching for a persisting template (added 2026-08-05, replacing a blunter "archive every line, recreate all fresh" behavior):** `_plan_schedule_sync` calls `_match_schedule_lines` once per persisting key, matching the survivor's current `attendance_schedule_ids` against the incoming entries by `(weekday, start_time, end_time)` - a line's own identity within a template. A line with no matching entry is archived outright (genuinely gone); a matched line whose room hasn't changed is left completely untouched; a matched line whose room *has* changed goes through the same decision as `ems.attendance_mixin._write_or_new_version` - updated in place if it has no real sessions yet, or archived-and-replaced-with-a-fresh-line if it does (split across the two passes above for the same cross-plan collision reason, not called as one atomic step - see the code's own comments on `_archive_stale_schedule_sync`/`_write_schedule_sync` for why). This is shared, unconditional model-level behavior - it applies identically whether the caller is the live Schedule tab's own edit or (once built) the working-schedule import wizard, not something either caller opts into separately.
- **Duplicate consolidation:** more than one active template can share the same (subject, group-set, teacher-set) key, a pre-existing data-quality artifact of repeated past imports. Only `templates[0]` (the "survivor") gets refreshed; every other duplicate sharing that key is archived outright.
- **History preservation:** stale data is always **archived**, never unlinked — `unlink()` itself refuses outright once any of a template's schedule lines has an actual `attendance_session_ids` entry (a real roll-call was taken against it).
- **`find_external_conflicts()`** is a read-only helper (used by the import wizard's preview and by the import itself) that finds active schedule lines belonging to teachers **outside** the current batch that would collide on room+time — a batch only cleans up its own teachers' stale data, so an external teacher's now-conflicting line needs separate handling.

## Access control

| Group | Access | Restriction |
|-------|--------|-------------|
| `ems.group_academic_admin` | Full CRUD | None (`security/rules/attendance.xml`: `rule_attendance_template_admin`, domain `[]`) |
| `ems.group_teacher` | Full CRUD | Own data only: `create_uid = user` **or** `teacher_ids.user_id = user` (`rule_attendance_template_teacher_own`) |
| `ems.group_secretary` | Read-only | None |

`read_only_user` (computed per-record, non-stored) additionally locks down the **form view** for a teacher looking at a template that passes the record rule via `create_uid` but isn't one of `teacher_ids` themselves (e.g. one co-teacher edited it, another can still see it under the OR domain above) — the ACL/rule layer decides *whether a row is visible/writable at the ORM level at all*, `read_only_user` decides whether *this specific viewer* should see editable widgets once it is.

## Known limitations

- **No default start/end date configuration** (`_plan_schedule_sync`'s `# TODO`): a new template's start date defaults to September 1st of the current year and end date to July 1st of the next, hardcoded — not read from any settings/course record.
- **Auto-assigned color is cosmetic only** — it exists to visually tell templates apart in the list view, nothing else reads it (no calendar/kanban `highlight_color` currently wired to it). See [Free-pick color widget](../shared/color_widget.md) for the rotation logic and the "all red" issue it replaced.
- **`study_ids` desync risk (reduced, not eliminated):** `_write_schedule_sync` sets it once from every involved group's own `study_id` at creation/sync time; if a template's `group_ids` is later edited by hand (only possible before `has_sessions`, see above) to groups from different studies, `study_ids` is not automatically recomputed to match — it only reflects the state at the last sync/manual edit. `_check_subject_valid_for_all_studies` still guards `subject_id` against whatever `study_ids` currently holds, so this can't silently produce an invalid subject/study combination, only a stale-but-internally-consistent one.

## Changed in this pass (2026-08-05)

`level_id` removed entirely (never used in any report, always derivable from `group_ids`/
`study_ids`); `study_id` (`Many2one`) → `study_ids` (`Many2many`), since a template can
legitimately cover groups from more than one study (co-teaching/"desdoble" across studies —
`_write_schedule_sync` now unions every involved group's own study). Added the
`has_sessions`-gated identity-field lock and "Edit" archive-and-clone action (both
here and on `ems.attendance_schedule`, see that doc). Converted `ems.attendance_session_header`'s
`group_ids`/`subject_id`/`space_id`/`template_teacher_ids`/`study_ids` from `sudo()`-laden
compute methods to genuine `related=` fields (see [`attendance_session.md`](attendance_session.md)).
Migration: `migrations/18.0.0.22.0/{pre,post}-migrate.py` (column rename + relation-table
backfill for the `study_id`→`study_ids` schema change).

**Later the same day:** extracted the archive-or-write decision behind `action_new_version()`
into a new shared mixin, `ems.attendance_mixin` (`models/shared/attendance_mixin.py`,
`_write_or_new_version(vals)`) - reused by the schedule-sync pipeline for its own per-line
decisions (see "CRUD flow" above), and intended for the working-schedule import wizard's future
room-reassignment step too (see `plans/working_schedule_import_redesign.md`), per the developer's
explicit reuse requirement rather than each caller reimplementing the same `has_sessions` check.
`_archive_stale_schedule_sync`/`_write_schedule_sync` changed from unconditionally archiving and
recreating *every* schedule line of a persisting template to a per-line match (unchanged lines
untouched, changed-without-sessions lines updated in place, changed-with-sessions lines
archived+recreated) - this is model-level behavior, not wizard-specific, so it applies to the
live Schedule tab's own edits too, not only a not-yet-built import path.

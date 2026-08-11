# Technical Reference: `ems.attendance_schedule`

## Overview

`ems.attendance_schedule` is a single weekly slot (weekday + start/end time + room) owned by
an [`ems.attendance_template`](attendance_template.md). A template groups everything about
"who teaches what, to whom, where" into one record; its `attendance_schedule_ids` are the
actual concrete weekday/time entries that make up that weekly timetable — e.g. a template
for "Maths, group A" might have two schedule rows: Monday 9:00–10:00 and Wednesday
9:00–10:00, both in the same room.

**This doc covers the model's own fields/logic.** The pipeline that creates, archives and
rewrites these rows from a teacher's live-edited or imported timetable
(`sync_from_schedule`/`sync_from_schedule_batch`) is documented in
[`attendance_template.md`](attendance_template.md) — not repeated here.

**Module file:** `models/attendance/attendance_schedule.py` (`EmsAttendanceSchedule`)

---

## Fields

| Field | Type | Notes |
|-------|------|-------|
| `weekday` | `Selection` ("0"=Monday…"6"=Sunday) | **Do not renumber** — matches Python's `date.weekday()` values exactly, several computes rely on this. |
| `name` | computed + stored | `"{template} \| {weekday} \| {time_range}"`, purely for the session form's dropdown sort order (SQL sort on a non-stored field wouldn't work). |
| `start_time`/`end_time` | `Float` | Hours as a decimal (e.g. `9.5` = 9:30). |
| `start_date`/`end_date` | `Datetime`, computed + stored | The template's own `start_date`/`end_date` (a plain date) combined with this schedule's `start_time`/`end_time`, converted local→UTC via `ems.datetime_utils` — stored as full datetimes because timezone-correct comparisons need a real date, not a bare time-of-day float. |
| `time_range` | `Char`, computed + stored | `"HH:MM - HH:MM"`, derived from `start_date`/`end_date` converted back to local time. |
| `teacher_ids` | `Many2many`, `related='attendance_template_id.teacher_ids'` | Read-only mirror, used **only** for `ir.rule` permission filtering (`security/rules/attendance.xml`) — not for any business logic in this file. |
| `has_sessions` | `Boolean`, computed | `True` once this line has a real `attendance_session_ids` entry — see "Locking" below for what this used to gate (now superseded by an unconditional lock). |

---

## Locking (the manual "Edit" button was removed 2026-08-11; extended to an unconditional field lock the same day)

**As of 2026-08-11, every field on this model except `student_ids` is unconditionally locked** via
a `write()` guard (`_LOCKED_FIELDS = {'active', 'weekday', 'start_time', 'end_time', 'space_id',
'attendance_template_id', 'notes'}`) - the same `EMS_BYPASS_TEMPLATE_LOCK_KEY` mechanism
`ems.attendance_template` uses (see that doc's "Access control" section). `security/
ir.model.access.csv` also revokes `create`/`unlink` for every group (matching the template's own
`1,1,0,0`) - a line can now only ever come into existence, change, or go away as a consequence of
the calendar-sync pipeline, never a direct edit, admin included. This widens what used to be a
narrower, `has_sessions`-gated lock (below, kept for history): changing where/when a class actually
happened after real roll-calls were taken against it would misrepresent that history
(`ems.attendance_session_header`'s own `space_id`/`weekday`/etc. are `related`+`store=True`
mirrors of these, see [`attendance_session.md`](attendance_session.md)) - the developer's own call
was that a direct edit is never legitimate regardless of session history, since it risks drifting
the line out of sync with the calendar even before any attendance was ever taken.

**Until 2026-08-11, a per-row "Edit" button (`action_new_version()`) let an admin/teacher unlock
one line by hand** - it archived this one line and cloned it under the same template, leaving the
template itself and every other line untouched (archive-before-copy, same reasoning as the
template-level version below: copying while the original line is still active would momentarily
collide with the clone via `check_overlap`). **Removed** as part of
`plans/calendar_driven_attendance_templates.md`'s point 3 (developer's own call: *"Este mecanismo
que hicimos para 'editar' templates o schedules ha quedado obsoleto"*) - now that the teacher's
calendar is the only legitimate source of change for a template's identity, a manual per-line
"Edit" escape hatch no longer fits; a room/time correction happens by editing the calendar instead
and letting the sync pipeline reconcile it.

**The underlying shared mechanism, `ems.attendance_mixin._write_or_new_version(vals)`
(`models/shared/attendance_mixin.py`), was NOT removed** - it's still used internally by the
schedule-sync pipeline (`ems.attendance_template._archive_stale_schedule_sync`/
`_write_schedule_sync`, see that model's "CRUD flow", which shares the exact same `has_sessions`
predicate for its own per-line decisions) and by the import wizard's own room-reassignment
conflict resolution (`working_schedule.py`, `line.right_schedule_id._write_or_new_version(...)`).
Only the direct, button-driven entry point on this model and `ems.attendance_template` is gone.

---

## Archiving never cascades to sessions, in either direction (settled 2026-08-06)

A same-day attempt added an `action_archive()` override here that cascaded to
`attendance_session_ids` - reverted the same day on developer feedback: a schedule line can be
archived for reasons that have nothing to do with a session's own relevance. Concretely, a line's
logistics fields (`weekday`/`space_id`/`start_time`/`end_time`) are locked (see "Locking" above) -
so a routine correction (fixing a room, say) doesn't edit the line at all, it
**silently** archives the old one and creates a new version via `_write_or_new_version()` above
(now only reachable through the calendar-driven sync pipeline or the import wizard's own conflict
resolution, not a direct button - see "Locking" above), entirely as a side effect of what looks
like a normal in-place edit from the calendar side. If that archive cascaded to sessions, every such routine correction would
make the line's whole attendance history disappear from a teacher's default view - exactly the
opposite of the intent (the sessions are still perfectly valid, current-course history; only the
room/time bookkeeping changed). `ems.attendance_session_header` ([`attendance_session.md`](attendance_session.md))
carries its own `active` (via the `ems.base` mixin, not something this model needs to populate)
but nothing in this codebase ever flips it automatically as a side effect of the schedule/template
that originally scheduled it being archived - `test_action_archive_does_not_cascade_to_sessions`/
`test_action_archive_on_template_does_not_cascade_to_sessions`
(`tests/test_attendance_template.py`) pin this down going forward. Sessions are never `unlink()`'d
either (see `unlink()` below) - they're an independent historical record, managed on their own
terms, not a dependent of either model. See
[`plans/course_transition_teacher_schedule_archival.md`](../../../../plans/course_transition_teacher_schedule_archival.md)
for the still-open question of how a teacher's session views should end up showing only the
current course's sessions, if that's still wanted - not via this cascade.

---

## `check_overlap`: double-booking guard with a co-teaching exception

```mermaid
flowchart TD
    A["check_overlap()\n@api.constrains(weekday, start_time, end_time, space_id)"] --> B{"template active AND\nhas start/end date?"}
    B -- no --> Z["skip — an inactive/incomplete\ntemplate can't conflict"]
    B -- yes --> C["search other schedules:\nsame weekday, active template,\ndate ranges overlap,\nsame teacher OR same space"]
    C --> D{"any candidate's time range\nactually overlaps?"}
    D -- no --> Z
    D -- yes --> E{"same teacher on both?"}
    E -- yes --> G["ValidationError:\n'...for the same teacher'"]
    E -- no --> F{"is_co_teaching_with(other)?\nsame subject AND shares\nat least one group"}
    F -- yes --> Z2["allowed — legitimate\nco-taught session"]
    F -- no --> H["ValidationError:\n'...for the same space'"]
```

The co-teaching exception exists because a single class session can genuinely have more
than one teacher assigned (support/co-teaching), each represented by their own
`ems.attendance_template` (since a template's `teacher_ids` is itself a set, but two
*separate* templates — one per teacher pairing — is how co-teaching is modeled here) — both
templates' schedules legitimately share the same room/time/subject/group without being a
real double-booking. `is_co_teaching_with()` is the shared predicate for this — also reused
by `ems.attendance_template.find_external_conflicts()` (see
[`attendance_template.md`](attendance_template.md)) against a not-yet-created entry dict,
since one side isn't a real record yet there.

## `find_schedule_lines_for_teaching`: reverse lookup from a calendar block to a schedule line

`ems.attendance_mixin.find_schedule_lines_for_teaching(teacher, subject, groups, weekday,
start_time, end_time)` (`models/shared/attendance_mixin.py`) — given a teacher + subject + a set
of groups + weekday + start/end time, returns every currently active line for that exact teaching
slot: subject match, ANY group overlap (not exact set equality — mirrors the same "same teaching
assignment" convention `ems.working_schedules_import_wizard._classify_conflict_kind` already
uses), and weekday/time overlap. **Deliberately NOT scoped by room** (renamed from
`find_schedule_lines_for_slot` and reworked 2026-08-10, after a real bug: the original version
also matched on room, and a real teacher's calendar block had drifted to a different room than
the schedule line's own — "el aula no es normal que cambie, [pero] no deberíamos usarla para las
búsquedas", since a teacher can freely change the room while taking attendance for an unplanned
reason (e.g. an unscheduled workshop) — matching on it silently broke this exact lookup the moment
that drift happened, leaving 4 real session headers stranded active in this dev DB despite their
own template/schedule already being correctly archived). If more than one line matches (e.g. a
stale leftover left behind by an earlier edit, alongside a newer one), every match is returned —
the caller decides what to do with each, not this lookup.

Called on the model itself, not a specific record — there is no natural `self` for a lookup like
this: `self.env['ems.attendance_schedule'].find_schedule_lines_for_teaching(...)`.

**Why it exists:** `resource.calendar.attendance` (a teacher's weekly calendar block) and
`ems.attendance_schedule` (the recurring class-session line) have no direct FK between them — the
link has always been purely inferred by matching (subject, group, weekday, time). The
course-transition archival cascade (`course_transition_wizard._apply_calendar_archival()`, see
[`course_transition_wizard.md`](../settings/course_transition_wizard.md)) needs exactly this
reverse lookup: given a calendar block being archived at transition, find which schedule line(s)
it backs, so the wizard can decide whether to archive that line (and its sessions) outright or
just drop this one teacher from a shared co-taught line.

**A genuinely bigger structural fix for this same inferred-link problem — replacing it with a real
FK from `resource.calendar.attendance` straight to `ems.attendance_schedule` — was proposed by the
developer the same day and written up in `plans/calendar_driven_attendance_templates.md`.** That
plan bundles four changes; only the FK (its point 4) has been built so far — see
`resource.calendar.attendance.attendance_schedule_id` below. The other three (moving `student_ids`
down to this model, locking template creation/archival to be calendar-driven only, and a
`(teacher_ids, group_ids, subject_id)` uniqueness constraint) remain proposed, not implemented —
this lookup is still the only way to answer "which line does this OLDER calendar block back" for
any block written before the FK existed, and still the fallback this method's own callers should
reach for if `attendance_schedule_id` is ever empty on a block that should have one (a bug, not
the normal case going forward).

## `resource.calendar.attendance.attendance_schedule_id`: the real FK (2026-08-11)

`resource.calendar.attendance` (`ems_working_schedule_assignation`,
`models/employees/working_schedule.py`) carries `attendance_schedule_id` (Many2one, this model) —
a genuine, always-correct link, replacing the inferred lookup above for every calendar block
written **from now on**. Cardinality is many-to-one, not one-to-one: co-teaching means each
co-teacher's own *personal* calendar gets its own `resource.calendar.attendance` row for the same
shared class, and all of them point at the same single `ems.attendance_schedule` line — the same
reason `ems.attendance_template.teacher_ids` is a Many2many rather than one template per teacher
(see [`attendance_template.md`](attendance_template.md)'s "Co-teaching" section).

**Captured by `ems.attendance_template._link_calendar_attendance(teacher_entries)`**, called at
the end of both `sync_from_schedule_batch` and `sync_from_schedule_batch_fresh_import` (right
after `_run_schedule_sync_plans` finishes writing the schedule lines for this same call — see
`attendance_template.md`'s "CRUD flow"). For every `(teacher, entries)` pair, it matches each
entry's own `(dayofweek, hour_from, hour_to)` against that teacher's own `resource_calendar_id.
attendance_ids` (freshly rewritten by the SAME import/edit call, immediately before this runs) to
find the calendar row, then reuses `find_schedule_lines_for_teaching` (above) to find the schedule
line it now maps to — writing the FK only when exactly one line matches. Reusing the same
inference here, rather than avoiding it entirely, is deliberate: at THIS point in the pipeline the
inference is trustworthy in a way a later, independent call (e.g. from a course transition run
months afterward) never can be — it runs inside the very same transaction that just archived every
stale/duplicate line for these exact entries (`_archive_stale_schedule_sync`'s survivor-picking,
see `attendance_template.md`), so there is no accumulated drift left to be ambiguous about. If a
match is still ambiguous (`!= 1` line) the FK is simply left unset on that row rather than guessed
— the same "leave it blank rather than guess" convention `_backfill_calendar_employee_and_course`
(`migrations/18.0.0.22.0/post-migrate.py`) already established for this same model's `employee_id`/
`course_id` backfill.

**No historical backfill.** Every `resource.calendar.attendance` row written before this phase
keeps `attendance_schedule_id` empty — populating it retroactively would mean re-running the exact
broad, ambiguity-prone inference this FK exists to stop needing, on data that's already had time to
drift (the same risk `find_schedule_lines_for_teaching`'s own docstring warns about). Any code that
still needs an older block's schedule line falls back to that lookup, unchanged, until the block
itself gets rewritten by a live edit or a re-import (which populates the FK from then on).
`course_transition_wizard._apply_calendar_archival()` (see
[`course_transition_wizard.md`](../settings/course_transition_wizard.md)) has **not** been switched
to read the FK yet — it still calls `find_schedule_lines_for_teaching` directly, since a real
production calendar can easily be full of pre-FK blocks for some time; a follow-up change can teach
it to prefer `attendance_schedule_id` when set and fall back to the lookup otherwise.

## `unlink()`: history guard

A schedule that already has `attendance_session_ids` (a real roll-call was taken against it)
cannot be deleted — the error message directs the user to archive the whole template
instead. This mirrors `ems.attendance_template`'s own archive-not-delete discipline (see
that doc's "History preservation" note) at the schedule-row level.

## Views

`views/attendance/attendance_schedule/form.xml` — embedded as a one2many tab on the
template's own form; no standalone list/menu of its own (schedules are always created and
edited in the context of their template).

## Fixed in this pass (2026-07-28)

Class renamed `ems_attendance_schedule` → `EmsAttendanceSchedule` (has its own `_name`, not
an `_inherit`-only extension). Whole file was tab-indented — normalized to spaces. Loop
variable `rec` → `schedule` throughout. `attendance_session.py` imported this class directly
by its old name (to reuse `weekdays_selection` on `ems.attendance_session_header.weekday`) —
updated to the new name. New `TestAttendanceScheduleLogic` test class (10 tests: computed
fields, `check_overlap`'s same-teacher/same-space/co-teaching/different-weekday branches,
the `unlink()` guard) — the existing `TestAttendanceScheduleAccess` class only covered the
`ir.rule` fix from an earlier session, not this model's own logic. No bugs found; no O work
needed (`_order`/constraints already correct).

## Changed in this pass (2026-08-05)

`action_new_version()` refactored to call the new shared `ems.attendance_mixin._write_or_
new_version()` instead of inlining its own archive+copy (the button itself was later removed
2026-08-11 - see "Locking" above).

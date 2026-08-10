Status: not started - proposed by the developer (2026-08-10), analyzed the same day, not yet
designed in detail. This file exists to not lose the idea and the open questions found while
sanity-checking it - re-verify against the current code before starting, since this plan may go
stale.

# Origin

Found while fixing a real bug (2026-08-10, same day): `ems.working_schedules_import_wizard`'s
course-transition archival (`ems.attendance_mixin.find_schedule_lines_for_teaching`,
`course_transition_wizard._apply_calendar_archival`) had to *infer* which `ems.attendance_schedule`
line a `resource.calendar.attendance` block corresponds to, because the two models have no direct
FK - only a content-matching convention (subject + group + weekday/time, room deliberately
excluded once we realized a teacher can freely change rooms while taking attendance). This works,
but it's inference, not a real relationship - exactly the class of bug this session's fix started
from (the original version matched on room too, and broke the moment a real room drifted).

While explaining that fix, the developer proposed a bigger structural change that would remove the
need for this inference entirely.

# The proposal

1. **Move `student_ids` from `ems.attendance_template` to `ems.attendance_schedule`** (i.e. from
   the whole template down to each individual weekly line). Rationale given: the only reason a
   teacher would create a genuinely *new* template today, rather than reuse an existing one, is a
   day-specific student roster difference (someone absent, someone extra attending) - if the
   roster lived on the line instead, a template would never need to fork just for that.
2. **Make `(teacher_ids, group_ids, subject_id)` unique per active template** - once roster and
   room both live below the template level, nothing about the template itself should ever need a
   second version for the same teaching assignment.
3. **Lock template creation/archival to be calendar-driven only.** A template's own schedule lines
   could still change room or student roster directly; the template itself (and whether it exists
   at all) would only ever be created or archived as a *consequence* of editing the teacher's
   calendar - never directly. The existing "reload" button (`reload_students`/`fill_students`)
   would need to move to the schedule-line level to match.
4. **Give `resource.calendar.attendance` a direct FK to its own `ems.attendance_schedule`** (and
   from there to `ems.attendance_template`), replacing the current inference-by-content matching
   with a real, explicit relationship.

Point 4 is the part that actually motivated this - once template existence is *derived from* the
calendar (point 3), the calendar block can carry the reference at the moment it (and the
schedule/template it implies) is created, instead of that link needing to be re-derived by content
matching every time something like a course transition needs it.

# What was actually verified before agreeing to anything (2026-08-10)

- **No active template pair today differs only by roster or room for the same
  (teacher, group, subject)** - checked directly against the real dev DB. The premise isn't
  contradicted by current data, but it also isn't confirmed as an already-observed problem; it's a
  forward-looking concern, not something already causing duplicates.
- **`student_ids` is NOT currently a locked "identity" field on the template** (only
  `teacher_ids`/`subject_id`/`group_ids`/`study_ids` are, per the `has_sessions` locking mechanism
  documented in `docs/en/developers/attendance/attendance_template.md`). Changing who attends an
  existing template is already a plain `write()` today - it does **not** trigger
  `_write_or_new_version()`/create a new template. A student missing one specific day is already
  handled at the `ems.attendance_session_line` level (that one session's own status), not by
  minting a new template.
- **Room changes already don't create a new template either** - a room change on an existing line
  goes through `_write_or_new_version()` at the `ems.attendance_schedule` (line) level, not the
  template level, matching the "Room reassignment" mechanism documented in
  `docs/en/developers/attendance/attendance_schedule.md`.
- So the specific motivating scenario ("a teacher creates a new template because of a one-day
  roster change") doesn't obviously match how template/schedule versioning actually works today -
  worth confirming with the developer whether this has actually been *observed* happening in
  practice (a teacher working around a UI gap by literally creating a duplicate template), or
  whether it's a hypothetical concern about a UI/permission gap that doesn't have a real trigger
  yet.

# Open questions ("flecos") to resolve before designing this for real

1. **Permissions**: `ir.model.access.csv` currently gives both `group_academic_admin` and
   `group_teacher` full CRUD (`1,1,1,1`) on `ems.attendance_template`, and neither the list nor
   form view sets `create="0"`/`duplicate="0"` - an admin or teacher *can* create/delete a template
   directly today, through the standard Odoo UI, independent of the calendar or the import wizard.
   Locking creation/archival to "calendar-driven only" means either revoking that direct access or
   intercepting `create()`/`unlink()` with new validation - a real behavior/permissions change to
   confirm is actually wanted, not something to assume.
2. **The FK doesn't appear "for free"** - for `resource.calendar.attendance` to carry a genuine,
   always-correct reference to its own `ems.attendance_schedule`, the write order has to change:
   today the working-schedule import wizard writes the calendar (`_write_teacher_schedule`) and
   syncs templates (`sync_from_schedule_batch_fresh_import`) as two related but independently-run
   steps, kept consistent by convention. Getting a real FK means one has to be *derived from* the
   other at write time (calendar written first, schedule/template created from it, capturing the
   FK then) - a real restructuring of `_apply_import()`'s own pipeline, not just a new column.
3. **`group_ids` is a Many2many** - a template can legitimately cover more than one group at once
   (a shared/co-taught class across two groups). "Unique per group" can't be a plain SQL
   `UNIQUE` constraint on that relation; it would need a Python `@api.constrains` checking for any
   group *overlap* between active templates for the same (teacher, subject) - the same shape of
   check `_classify_conflict_kind`/co-teaching detection already does elsewhere in this codebase,
   so there's a precedent to reuse, but it's still new code to write and test.
4. **The "New"/copy-from-another-teacher panel on the Schedule tab, and the `reload_students`
   button**, both currently operate at the template level and would need to move to the schedule-
   line level to match point 1 above - not yet looked into how much of their own logic assumes
   template-level `student_ids`.
5. Does `_write_or_new_version()`'s template-level locking still need to cover anything once
   student roster and room both move down to the schedule line? `teacher_ids` (co-teaching
   changes, e.g. the course-transition scenario this session's fix was about) still seems like a
   genuine template-level identity change that needs the same has_sessions-aware archive+clone
   protection - so the mechanism itself likely survives, just with a narrower scope (only
   `teacher_ids`/`subject_id`/`group_ids`/`study_ids`, same as today, just nothing left to *add*
   to that list - roster and room were never on it to begin with, per the point above).

# Recommendation for whoever picks this up

This is a genuine, worthwhile simplification (point 4 in particular directly removes the class of
bug this session just fixed by inference instead of a real relationship) - but it's a
redistribution of responsibility across three models (calendar, schedule, template), touching
permissions, the import wizard's write pipeline, and two UI panels on the Schedule tab. Treat it as
its own Spec/Red/Green cycle (per this repo's Development workflow), not an extension of the
room-matching fix this session already shipped and tested - confirm answers to the "flecos" above
with the developer before writing any code, especially #1 (permissions) and #5 (whether the
locking mechanism's scope actually needs to change or just narrows on its own).

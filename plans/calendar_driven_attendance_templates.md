Status: IN PROGRESS (2026-08-11) - GitHub issue #372. Point 4 (the direct FK) is DONE - see
"Point 4: implemented 2026-08-11" below. Points 1-3 are still proposed, not implemented, per the
developer's own explicit choice to do the FK first and defer the rest (asked via AskUserQuestion,
2026-08-11: "Solo el FK (fase 2)"). Re-verify against the current code before starting the next
phase, since this plan may go stale between sessions.

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

# Migration requirement found while investigating a real import bug (2026-08-11)

Real scenario: an admin merged two raw file identifiers to the same already-existing teacher on
the "Resolve teachers" screen, completed the import, and found the teacher had `ems.teaching` rows
(subject/group assignments - written independently by `ems.teaching.sync_from_schedule`) but an
EMPTY "Schedule" tab, with the UI showing "No working schedule assigned to this employee yet."

**Root cause, confirmed against this dev DB, unrelated to the two-identifier merge (would happen
identically for a single identifier) and unrelated to course transition (ruled out - see below):**
`_write_teacher_schedule()` (`models/employees/working_schedule.py`) does
`teacher.resource_calendar_id.write({'attendance_ids': attendance_ids})`, documented as assuming
"every teacher already has one, auto-created at `employee.create()` time." That auto-creation
(`hr.employee.create()`'s override, `models/employees/employee.py`) was only introduced in commit
`bc29e04b` (version `18.0.0.20.0`, 2026-07-12) - it never runs for an employee already in the
database before that date, and `write()` has no equivalent logic for an employee whose
`employee_type` becomes `'teacher'` later. The one migration written around that same version
(`migrations/18.0.0.20.0/post-migrate.py`) only backfilled employees whose `resource_calendar_id`
pointed at the OLD shared company calendar being retired that same migration - it never checked for
`resource_calendar_id IS NULL` on its own, so an employee who was already NULL (not pointing at the
old calendar at all - the likely path for anyone created via a backend data import rather than
through the UI, since the client-side default that would otherwise fill it in doesn't apply there)
fell through that migration's own detection net too. **Confirmed via `psql` (2026-08-11): 8 active
`hr.employee` (`employee_type='teacher'`) rows in this dev DB have `resource_calendar_id IS NULL` -
every one of them `create_date`s well before 2026-07-12, consistent with this exact gap, not a
one-off.** No `mail_tracking_value` history shows any of them ever having `employee_type` changed
after creation either, ruling out "created as a different type, converted later" as a contributing
case for these 8 specifically.

**Course transition explicitly ruled out as a cause**, per the developer's own suspicion, confirmed
by reading the code: `course_transition_wizard._apply_calendar_archival()` only ever collects
`affected_teachers` from `_migrating_calendar_blocks()` - teachers who already HAVE calendar
attendance blocks to migrate. A calendar-less teacher produces zero blocks, so they're never
included, and `_apply_calendar_rollover()` (which reassigns `resource_calendar_id` for archived-and-
rolled-over teachers) never runs for them either. If anything, a calendar-less teacher who *did*
somehow reach `_apply_calendar_rollover()` would come out the other end WITH a fresh calendar (its
first line reads `calendar = teacher.resource_calendar_id`, then unconditionally creates/reactivates
`next_calendar` and assigns it) - that code path is self-healing, not a source of this bug.

**What the eventual migration for this redesign (or, if this lands sooner, a dedicated one) must
include:** a backfill creating a personal `resource.calendar` (mirroring `hr.employee.create()`'s
own logic - `employee_id`, `course_id`, `seed_from_framework(company.default_schedule_framework_id)`)
for every `hr.employee` with `employee_type = 'teacher'` and `resource_calendar_id` falsy, active or
archived. Worth doing as part of whichever migration folder is current when this redesign (or a
narrower fix) actually ships, so any teacher created before this gap was ever closed - anywhere,
not just this centre's own dev data - is covered before that install's own batch importer next
runs against them. Point 2 in "Open questions" above (the FK not appearing "for free," the calendar/
schedule/template write order needing to change) makes this backfill directly relevant to this same
redesign, not a tangential concern - the redesign's own success depends on every teacher genuinely
having a calendar to hang the new FK off of, which today's data confirms isn't yet universally true.

# Point 4: implemented 2026-08-11

`resource.calendar.attendance.attendance_schedule_id` (Many2one to `ems.attendance_schedule`)
exists and is populated automatically at the end of every schedule sync
(`ems.attendance_template._link_calendar_attendance`, called from both `sync_from_schedule_batch`
and `sync_from_schedule_batch_fresh_import`) - see `docs/en/developers/attendance/
attendance_schedule.md`'s own section on this field for the full mechanism, and
`changelog/372-move-students-from-attendance_template-to-attendance_schedule.md` for what shipped.

**Deliberately no historical backfill** - a `resource.calendar.attendance` row written before this
phase keeps `attendance_schedule_id` empty. This matters directly for the production-migration
sequencing below: any "which templates have no calendar backing them" check based purely on this
FK will show a FALSE POSITIVE for every template whose calendar hasn't been through a fresh sync
since this phase shipped - not just genuinely orphaned ones. See the caveat under step 1 below.

# Production migration sequencing (developer's own plan, 2026-08-11)

Explained by the developer for when ALL FOUR points above are implemented (they're explicit that
this can wait until then) - captured here now so it isn't lost by the time that happens:

1. **Audit/cleanup pass**: once the calendar is authoritative, no active `ems.attendance_template`
   should exist without real calendar backing - any that do ("custom", i.e. created by hand,
   bypassing the calendar) should be archived.
2. **Course transition**: every teacher's `resource.calendar` "goes blank" for the new course,
   which should imply archiving every `ems.attendance_schedule`/`ems.attendance_template` those
   calendars were backing.
3. **Re-import**: loading the new course's schedules via the importer creates the new
   `resource.calendar.attendance` rows, which in turn create the `ems.attendance_template`/
   `ems.attendance_schedule` records (with the FK already attached, per point 4 above).

**Confirmed/refined with the developer (2026-08-11):**

- **Step 2 is confirmed intentional, not an approximation**: the developer explicitly wanted the
  OUTGOING calendar to stay queryable for future reference (this is exactly why `employee_id`/
  `course_id` were added to `resource.calendar` in the first place, see
  `plans/course_transition_teacher_schedule_archival.md`) - archiving the whole calendar and
  pointing the teacher at a fresh one is the deliberate design, not something to "fix" into
  literally blanking the calendar in place. `_apply_calendar_rollover()` already does exactly this
  and needs no rethink here.
- **Step 1 simplified: archive everything and regenerate from the CURRENT calendars, rather than
  trying to detect which templates are genuinely "orphaned"** (developer's own call, sidestepping
  the FK-backfill-gap false-positive problem entirely - the FK-based orphan detection above is no
  longer needed for this). Since the calendar is authoritative once points 1-3 land, archiving
  every active `ems.attendance_template` outright and then re-running the normal sync for every
  teacher's CURRENT `resource.calendar.attendance` rows reconstructs an equivalent, fully
  calendar-backed set from scratch - there's no need to first classify old data as "orphan" vs.
  "legitimate" when the plan is to rebuild all of it from the same source of truth anyway.
  Concrete design notes for whoever writes this script, so they don't need to re-derive them:
  - Archiving a template never touches its real attendance-session history (see "Archiving never
    cascades to sessions" in `attendance_schedule.md`) - a real class's past attendance stays
    intact and queryable against the archived template/schedule, exactly like a normal
    `action_new_version()` correction. Safe to archive unconditionally.
  - Regeneration should read every non-framework calendar's CURRENT `attendance_ids`, convert each
    teaching row back into an `entry` dict (the same shape `sync_from_schedule_batch*` already
    expects: `subject_id`, `group_ids`, `dayofweek`, `hour_from`, `hour_to`) **explicitly including
    each row's own `space_id`** (not left to default from the group) - `resource.calendar.
    attendance.space_id` is a plain stored field that can already diverge from the group's own
    default (a prior room reassignment), and `_schedule_line_vals`'s own `entry.get("space_id",
    space_id)` fallback only preserves that divergence if the entry dict actually carries it.
  - Feed every teacher's full entry list through `sync_from_schedule_batch` (the LIVE-EDIT variant,
    "this call = the teacher's whole current schedule" semantics), not
    `sync_from_schedule_batch_fresh_import` (the importer's own "one slice" semantics) - a
    regeneration pass genuinely IS each teacher's entire current schedule, all at once, so the
    stricter live-edit reconciliation is the semantically correct one here, even though nothing
    strictly depends on it once every template was already archived first.
  - This naturally re-populates `attendance_schedule_id` on every calendar row too (point 4's own
    mechanism, unchanged) - by construction, nothing produced by this regeneration can be a false
    "orphan" under the FK, since it was JUST created by the same sync that sets the FK.

# Recommendation for whoever picks this up

This is a genuine, worthwhile simplification (point 4 in particular directly removes the class of
bug this session just fixed by inference instead of a real relationship) - but it's a
redistribution of responsibility across three models (calendar, schedule, template), touching
permissions, the import wizard's write pipeline, and two UI panels on the Schedule tab. Treat it as
its own Spec/Red/Green cycle (per this repo's Development workflow), not an extension of the
room-matching fix this session already shipped and tested - confirm answers to the "flecos" above
with the developer before writing any code, especially #1 (permissions) and #5 (whether the
locking mechanism's scope actually needs to change or just narrows on its own).

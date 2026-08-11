Status: ✅ COMPLETE (2026-08-11) - GitHub issue #372, all 4 points implemented and tested (see
"Point 4: implemented 2026-08-11" and "Points 1-3: implemented 2026-08-11" below).
`regenerate_all_from_calendars()` (see "Production migration sequencing" below) is now also built
for real and wired into this version's own migration (`migrations/18.0.0.22.0/post-migrate.py`),
not just a design reference - see "Production migration sequencing: built for real, 2026-08-11"
below for what changed from the original design. A further lock refinement (point 3 tightened,
`space_id` removed from the template) shipped the same day - see "Calendar-lock refinement:
schedule lines and remaining template fields, 2026-08-11" below. This file can be deleted once
the change is merged and the migration has actually run somewhere real - see CLAUDE.md's own
"Design plans" convention.

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

# Points 1-3: implemented 2026-08-11

See `changelog/372-move-students-from-attendance_template-to-attendance_schedule.md` for the full
write-up (what shipped, every real write path touched). Summary:

- **Point 1 (`student_ids` moved to the schedule line)**: done, including the data migration
  (each template's roster copied onto every one of its lines, old relation table dropped) and
  every real write path (`ems.attendance_session_header._auto_populate_lines`, `ems.enrollment`'s
  add/remove sync hooks, `res.partner._ems_clear_operational_records`). UI: a "Students" button
  per schedule-line row opens that line's own form (a full roster doesn't fit an inline list row).
- **Point 2 (uniqueness)**: implemented as an EXACT-match `@api.constrains` on `ems.attendance_
  template` (`(subject_id, teacher_ids-as-set, group_ids-as-set)`), not the broader "any group
  overlap" the plan originally floated - confirmed with the developer that overlap alone would
  wrongly reject a real, legitimate "desdoble" pattern already present in this centre's own data
  (same teacher/subject, one template for a group alone, another for that group combined with
  another, on different days). 0 real exact-duplicate conflicts existed in this dev database, so
  no data cleanup was needed before turning the constraint on.
- **Point 3 (calendar-driven only)**: `create`/`unlink` revoked in `security/ir.model.access.csv`
  for every group, admin included (developer's own final call, after confirming
  `_templates_to_archive()`'s study-scoped search already handles a manually-created template
  correctly at course transition - no orphan risk). Manual archival additionally hard-blocked by a
  new `write()` override (CSV alone can't express "no archiving via `active` but yes to other
  writes" at that granularity). The manual "Edit" button (`action_new_version`) was removed
  entirely as obsolete, on the developer's own call - the underlying shared mechanism
  (`_write_or_new_version`) stays, since `course_transition_wizard` and the import wizard's
  own conflict resolution still use it internally.

**No longer deferred:** `regenerate_all_from_calendars()` (originally considered as a prerequisite
for point 2, then deferred since the exact-match constraint turned out to be safe without it) is
now built for real - see "Production migration sequencing: built for real, 2026-08-11" below.

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

# Production migration sequencing: built for real, 2026-08-11

Confirmed against a real production snapshot (`ems_v18.0.0.21.0_2026-08-06_14-57-15.zip`,
restored into an isolated `ems_372_migration_test` DB - never the live `ems`/`ems_prod_snapshot`
databases): 2 real exact-duplicate `ems.attendance_template` pairs existed, which the new
uniqueness constraint (point 2) would otherwise reject on upgrade. The first approach tried was a
one-time migration step that detected and MERGED each duplicate pair (survivor = earlier
`start_date`, loser's non-conflicting schedule lines reparented onto the survivor). It worked
(after being redesigned to merge per schedule-line, once a real double-booking conflict was found
on the very first snapshot test - see the git history of `migrations/18.0.0.22.0/post-migrate.py`
for that abandoned version) but the developer then questioned whether the whole effort was
worthwhile, given `regenerate_all_from_calendars()` was already going to archive and rebuild
everything at the eventual course transition anyway: **"¿tiene sentido el esfuerzo de fusionar, si
se va a proceder a archivar todo y recrearlo en función del calendario del docente?"**

**Decision (developer's own call): drop the merge migration entirely. Instead, run
`regenerate_all_from_calendars()` itself as part of THIS SAME migration** (not deferred to a
separate, later course-transition event) - confirmed viable specifically because it runs inside
`post-migrate.py`, before module data reloads finish and before the Odoo service is reachable by
any user: the archive+rebuild is never visible as an intermediate broken state, since nobody can
hit the app until it's already done. This makes step 1 of the original 3-step sequencing above
(audit/cleanup) happen automatically, immediately, as a side effect of deploying this version -
not a separate manual step to remember to run later. Steps 2 (course transition) and 3 (re-import)
are unaffected and still happen at the real, later course-transition event, using the SAME
`regenerate_all_from_calendars()` method (now with an optional `teachers` recordset parameter,
added so a test - or a future partial/admin-triggered regeneration - can scope it without touching
every teacher in the database) if a "re-audit" is ever wanted at that point too, though the
course-transition wizard's own existing archival flow already covers that case on its own terms.

Why the merge's complexity became unnecessary: `sync_from_schedule_batch` groups entries by
`(subject, group-set, teacher-set)` - by construction, it can never produce two templates for the
literal same combination. Archiving everything first and rebuilding from the CURRENT calendar
state (the same source of truth points 1-4 already make authoritative) naturally yields a
non-duplicated set with zero special-cased merge logic. An orphaned template with no real calendar
backing (the actual nature of one side of both dev-DB/production duplicate pairs found during
testing - a stray, never-synced-to-the-calendar leftover) simply isn't recreated at all; a
double-booking that genuinely exists in the current calendar data still surfaces via
`check_overlap`, exactly like any other sync - a real conflict a migration must never silently
resolve.

**This is a breaking change**, called out explicitly by the developer: a teacher whose working
schedule was never (re)loaded onto their personal `resource.calendar` ends up with zero active
templates after this migration, and cannot take attendance until it is - there is no way to route
around this, since the whole point of points 1-4 is that a template only ever exists as a
consequence of a real calendar. See `changelog/372-move-students-from-attendance_template-to-attendance_schedule.md`'s
"Breaking changes" section.

**Real finding while re-testing the simplified migration against the real production snapshot
(`ems_372_migration_test`, isolated, restored from `ems_v18.0.0.21.0_2026-08-06_14-57-15.zip`,
2026-08-11):** the migration correctly ABORTED on its first run - `check_overlap` caught a genuine
room double-booking ('Carlos Casas' teaching "TUT ASIX1: Tutoria" vs 'Priscila Rodríguez' teaching
"MP 0369: Implantació de sistemes operatius", both Wednesday 18:15-19:10, room "Stallman (0.01)",
group ASIX1A) - proof the safety design works as intended (a real conflict surfaces loudly instead
of being silently merged away).

A follow-up read-only SQL scan of this same isolated snapshot (mirroring `check_overlap`'s own
logic: same room+weekday+overlapping time, excluding the co-teaching exemption - same subject_id
AND a shared group) found **40 distinct real overlapping teacher-pairs**, not just the one that
happened to abort the migration first. These are heavily concentrated on a handful of specific
teachers appearing opposite a *different* primary teacher across MANY different subjects in the
same room/time slot every day of the week - e.g. 'Priscila Rodríguez' opposite 5 different
teachers across "MP 0369", "MP 0372", "MP OPT2", "MP 0484", "MP 0483"; 'Inma Martínez' opposite 3
different teachers across "MP 0438"/"MP 0439"/"MP 0442"; 'Juan Zabay'/'Laura Martín' both opposite
'Eric Bautista' across several AIF subjects.

**Confirmed with the developer (2026-08-11): this is exactly a support/reinforcement co-teaching
pattern** ("Priscila és una profesora que ha estado haciendo de refuerzo... Entiendo que el resto
también"). The developer also confirmed the design goal driving the fix below: **this version
should be deployable on any live EMS instance directly, without first requiring a course
transition to blank every calendar** - checked whether the normal course-transition + reimport
path would sidestep this problem "for free", and it does NOT: the working-schedule import wizard's
own `_classify_conflict_kind` has the exact same gap (a matching-subject requirement for
`co_teaching_eligible`), classifies this cross-subject/same-room case as `plain_conflict`, and
`_resolution_is_valid` only allows `{reassign_rooms, prevail_left, prevail_right}` for that kind -
no "confirm both as co-teaching" option exists there either. So the normal reimport path would hit
the identical 40 cases, one by one, with only a fictional room reassignment or dropping one side
as options - not actually a solved problem, just deferred to a slower, per-conflict manual UI.

**Fix, per the developer's explicit design ("debemos archivar la que corresponde al refuerzo (o la
que creemos que es de refuerzo, o una de las dos sin más)... diciendole lo que se ha archivado, y
con que entraba en conflicto, le damos las herramientas para que pueda entrar y tocar calendarios a
mano"):** deliberately does NOT widen `is_co_teaching_with`/`check_overlap` themselves - both are
general-purpose, used by every live schedule edit, and loosening them risks masking a genuine
future double-booking mistake (the far more common real shape of this exact same "different
subject, same room/slot/group" pattern). Instead, `ems.attendance_template.
_drop_unresolved_conflicts` runs inside `regenerate_all_from_calendars()`, before the sync: scans
every teacher's entries pairwise for this exact clash shape and drops ONE side (arbitrary
iteration-order choice, no attempt to guess which one is "really" reinforcement) so the batch still
completes. The migration logs every dropped entry by name (teacher, subject, weekday/time, room)
and what it conflicted with, so whoever runs it knows exactly which pairs need a manual fix via the
Schedule tab afterward - same "breaking change, needs manual follow-up" contract as a teacher with
no schedule loaded at all. See `ems.attendance_template.regenerate_all_from_calendars`'s and
`_drop_unresolved_conflicts`'s own docstrings, and `docs/en/developers/attendance/
attendance_template.md`, for the implementation.

Separately, and unrelated: the same class of issue was also found incidentally in the *current
dev DB* (`ems`, not production - see CLAUDE.md's sandbox/prod distinction) while testing
`regenerate_all_from_calendars()`'s own test coverage - 'Eric Bautista'/'Christian Escobar' both
currently hold a Friday 16:00-17:00 slot in 'Aula 1.21' for two different subjects. Not
investigated further.

# Calendar-lock refinement: schedule lines and remaining template fields, 2026-08-11

The developer found two live gaps in point 3's original lock, still open to direct edits through
the normal UI even after the earlier work:

1. **`ems.attendance_schedule` lines could still be added/removed/edited by hand** - `create`/
   `unlink` were still `1,1,1,1` in `security/ir.model.access.csv` (never revoked, unlike the
   template), and every field (`weekday`/`start_time`/`end_time`/`space_id`/
   `attendance_template_id`/`notes`) was freely writable - only the template's own embedded list
   view showed them `readonly="has_sessions"` (a view-only hint, not an ORM guard, and only while a
   line had no real sessions yet).
2. **`ems.attendance_template`'s own identity fields were still writable** - point 3 only ever
   locked `active`; `teacher_ids`/`subject_id`/`group_ids`/`study_ids`/`start_date`/`end_date`
   stayed a plain `write()` for admin/teacher. Developer's own words: *"ni siquiera el admin
   debería poder cambiar esos datos, para no generar inconsistencias. Los cambios deberían venir
   siempre desde el calendario."* Also flagged `space_id` on the template as no longer needed.

**Fix, mirroring point 3's own mechanism exactly:**
- `ems.attendance_schedule` gained its own `write()` guard (`_LOCKED_FIELDS = {'active', 'weekday',
  'start_time', 'end_time', 'space_id', 'attendance_template_id', 'notes'}`) - only `student_ids`
  stays freely writable. `security/ir.model.access.csv` revokes `create`/`unlink` for every group,
  matching the template's own `1,1,0,0`.
- `ems.attendance_template._LOCKED_FIELDS` extended from just `{'active'}` to also include
  `teacher_ids`, `subject_id`, `group_ids`, `study_ids`, `start_date`, `end_date` - only `color`
  stays freely writable.
- `space_id` removed from `ems.attendance_template` entirely (not just locked) - it only ever
  existed as a default-value source for manually adding a schedule line, itself no longer possible
  either. `ems.attendance_schedule.space_id` (the line's own room) is unaffected and unchanged.
- `ems.attendance_mixin._write_or_new_version`'s in-place branch didn't carry the bypass context at
  all (only its archive+copy branch did) - fixed to bypass both branches consistently, since it's
  shared by both models and every legitimate internal caller on either one now needs it.
- Every legitimate internal write/archive site across `attendance_template.py` (the sync pipeline's
  own line rewrites/archives, the survivor's nested-line creates) and `working_schedule.py` (the
  import wizard's room-reassignment resolution) updated to carry the bypass context (and `sudo()`
  where a nested schedule-line `create()` is now involved, since that's ACL-revoked too).
- Views updated: the template form's identity fields are unconditionally `readonly="1"` now (not
  conditional on `has_sessions`/role); the embedded schedule-line list lost its `space_id` column,
  gained `create="0" delete="0"`, and its remaining columns are unconditionally readonly too.

See `docs/en/developers/attendance/attendance_template.md` and `attendance_schedule.md` for the
full technical writeup once updated in the same pass as this note.

# Follow-up questions raised alongside this refinement (2026-08-11) - all resolved same day

**1&2. Is `_write_or_new_version` still needed once templates/schedules can't be edited by hand?**
Yes - it's used by two legitimate INTERNAL processes, never a direct user edit, both indirectly
triggered by "the calendar" (an import file, or a course transition), consistent with the whole
design: `working_schedule.py`'s import-wizard room-reassignment resolution
(`line.right_schedule_id._write_or_new_version({'space_id': ...})`), and `course_transition_
wizard.py`'s departing-co-teacher correction (`template._write_or_new_version({'teacher_ids':
[(6, 0, remaining.ids)]})`). Confirmed via a full grep of every call site - no other callers exist.
Not changed; already correctly bypasses the write-lock via `EMS_BYPASS_TEMPLATE_LOCK_KEY` (both
branches, since this same refinement fixed the in-place branch not carrying it - see above).

**3. Mid-course subject handoff on the same weekly slot** — **implemented, 2026-08-11.** Developer's
own proposed approach (simpler than the (a)/(b)/(c) options originally floated): `ems.attendance_
schedule.check_overlap()` already filters candidates by TEMPLATE date-range overlap - two
templates with non-overlapping dates for the same slot were already safe, the only real gap was
that `resource.calendar.attendance` (the actual source of truth) had no date concept at all, so
the sync pipeline always defaulted every template to the full course year regardless. No cron or
"staged future edit" needed - the admin just enters both halves of the year upfront, each with its
own explicit date range, and the existing overlap logic does the rest. See
`docs/en/developers/employees/working_schedule.md`'s own "Mid-course subject handoff" section for
the full implementation writeup (reuses core Odoo's own `date_from`/`date_to` fields on
`resource.calendar.attendance` - NOT new EMS fields, confirmed the hard way after a first draft
that added parallel EMS-only fields collided with core's own `_check_overlap` constraint, which
deliberately excludes any row that already has `date_from`/`date_to` set from its "no overlap"
scan). Interactive coverage: `static/tests/tours/working_schedule_split_period_tour.js` +
`tests/test_working_schedule_split_period_tour.py`.

**4. Discarded - developer's own call, 2026-08-11:** *"lo descarto porque el PAS no da clase pero
tendrá calendario, así que creo que es mejor no juntarlo."* (PAS/support staff will have their own
calendar without ever teaching - merging session/attendance-taking machinery into the calendar
model would inappropriately couple it to a model that also has to represent non-teaching-only
calendars.) Consistent with the earlier technical assessment (deliberately incompatible calendar-
vs-schedule lifecycles, see the git history of this file for the full reasoning) - keep the
three-layer split (calendar → schedule → session), not something to revisit without a much more
concrete problem this would solve.

# Further refinements on top of point 3, same day (2026-08-11)

**Weekly hours summary must count a date-split slot once, not twice** - developer's own call:
*"el conteo cuando se solapan debe funcionar bien. Si hay 2 sesiones en el mismo bloque con fechas
distintas, hay que contarlo como una sola sesión (la más larga)."* Implemented via
`resource.calendar._dedupe_date_split_blocks()`, called from `get_schedule_hours_summary()` - see
`docs/en/developers/employees/working_schedule.md`'s own "Date-split slots count once, not twice"
note for the implementation.

**Schedule tab edit-mode UI redesign: shared period rows → independent per-day cards** -
developer's own call, after seeing point 3's first-draft widget: *"no me gusta el widget, porque
las fechas de inicio/final son para toda la fila y queda raro. Además todo queda demasiado
apretado."* Full spec given (5 day columns, independent cards each with its own start/end date,
start/end time, subject-or-non-teaching-reason, groups, room; a "+ Add" button per column; no
drag-and-drop; the view/calendar mode staying pixel-identical to before) and confirmed feasible
before implementing. Framework scaffolding kept (option 2 of the two proposed) - developer's own
call: *"Vamos a partir de la 2, creo que eso hará más fácil mostrar los patios en el modo
edición"* (a future feature, not yet built). See `docs/en/developers/employees/working_schedule.md`'s
own "Schedule tab widget's own UI for this" writeup for the full implementation, and
`static/tests/tours/working_schedule_split_period_tour.js` for the rewritten interactive coverage.

**Real bug found and fixed while reviewing the card redesign: derived breaks (patio) missing on
days a teacher's real entries didn't happen to span into the break's own hour.** Found by the
developer testing two real teachers after the redesign - one (Fernando Porrino) whose real
calendar alternates morning-only some weekdays / afternoon-only others (a dual-shift vocational
pattern), one (Juan Zabay) who works afternoon-only every day but was still shown a morning break
that never applied to him, while his own real afternoon break didn't show at all. Root cause: the
original `hr.employee._get_derived_break_entries()` computed containment against each individual
DAY's own known span - correct for a teacher with a single, uniform daily pattern, but wrong for
one whose real classes vary morning/afternoon by weekday. Redesigned (2026-08-11) to compute a
WHOLE-WEEK morning/afternoon span instead - developer's own spec: *"si el docente trabaja de
mañana, se muestra siempre el patio de la mañana [...] de tarde [...] de mañana y tarde, se
muestran ambos [...] aunque ese día el docente no trabaje."* See
`docs/en/developers/employees/working_schedule.md`'s own "Derived break" section for the full
writeup, including why classification recomputes morning/afternoon from `hour_from` rather than
trusting the stored `day_period` field (a real, pre-existing inconsistency between two different
write paths' own thresholds). Verified empirically against both real teachers' actual calendars
via `get_derived_break_attendance_data()` (not just backend tests) before considering it fixed.

**A second, separate real bug found while re-testing this fix on more real teachers (Gabriel
Manrubia): the widget kept showing a PREVIOUSLY viewed teacher's own derived breaks/hours summary
after paging to a different one.** Root cause: `schedule_grid_field.js` only loaded these two from
`onWillStart` (mount-only) - Odoo's form view reuses the same widget component instance across a
pager navigation (no remount), so a mount-only load never refreshed. Fixed with `useRecordObserver`
- with a real subtlety: the hook's own `record` argument must be used, not `this.props.record`,
which can still be the previous employee at the exact moment the callback fires (confirmed the
hard way - a first attempt using `this.props.record` was still broken). Regression-tested by
`static/tests/tours/working_schedule_stale_breaks_tour.js`.

**A third refinement, the same developer report: candidate breaks were being searched across
EVERY framework unconditionally, so a teacher genuinely teaching only a CCFF program (CFGS/EFPS)
was shown their own program's break correctly, but ALSO two unrelated ESO breaks that happened to
fit by time alone.** Developer's own proposed design, implemented as given: candidates now scope
to `teaching_ids.group_id.level_id` (the level(s) the teacher actually teaches, kept in sync with
the real calendar) - falls back to searching every framework only when the teacher has no
identifiable level at all. A teacher spanning several levels whose frameworks share the same break
(ESO/Batxillerat, at this centre) needs no special-casing, the existing dedup already collapses it;
one genuinely spanning different configurations sees only their own relevant breaks. Verified
empirically against the reporting teacher's real calendar plus two others checked earlier in the
same investigation - all three now show exactly the expected breaks, nothing more.

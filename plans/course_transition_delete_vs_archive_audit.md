Status: not started - proposed by the developer (2026-08-10), after fixing several course-
transition archival gaps the same day (see `project_course_transition_attendance_archival_gaps`
in memory). Re-verify the model list below against the current code before starting, since
`_apply_cleanup()`/`_ems_clear_operational_records()` may have changed since this was written.

# Origin

While fixing real leftover "daily issue"/justification data left un-archived by the course
transition wizard, the developer asked directly: *"¿Estás borrando issues? Habría que archivar,
no borrar."* The answer, confirmed the same day: the NEW code added this session only ever
archives (`action_archive()`), never deletes - the deletion the developer was seeing comes from a
**pre-existing** method, `res.partner._ems_clear_operational_records()`
(`models/contacts/contact.py`, added 2026-07-27 with the course transition wizard itself, not by
this session's work), which genuinely does `unlink()` several models for a student **actually
leaving the centre** in that specific transition run.

The developer's own framing for why this might be fine: *"Comenté con Juan que, una vez
transicionado el curso, seguro que podían borrarse entradas que ya habían quedado grabadas como
parte del histórico."* - i.e. once something is safely captured in a historical record, deleting
the live copy is expected to be harmless. That conversation with Juan was never turned into a
concrete audit - this plan is that audit, for later.

# The question to actually answer, per model

For every model touched by `_apply_cleanup()` (course transition) or
`_ems_clear_operational_records()` (shared with the withdrawal wizard): **is deleting it safe
because its information already lives somewhere read-only/historical, or does deleting it lose
detail nothing else preserves?** Two failure directions to watch for, not just one:
- A model currently **deleted** that turns out to lose real detail nobody kept elsewhere - should
  switch to `action_archive()` instead (matching this session's own "archive, never delete, for
  historical attendance data" pattern already applied to templates/schedules/sessions/
  justifications/issues-outside-scope).
- A model currently **archived** (by this session's own new code, or pre-existing) that turns out
  to be fully redundant with something already frozen elsewhere - could reasonably switch to
  deletion instead, if archiving it forever serves no purpose and just accumulates dead rows.

# What's already known, as a starting point (verified 2026-08-10)

**The one confirmed "already captured elsewhere" model: `ems.student.year_record`** (+ its
`.subject`/`.outcome` children, `models/grades/year_record.py`) - a dedicated, plain-data snapshot
model (Char/Integer/Float fields, not live FKs to the things it summarizes) frozen once per
student per course by `_apply_history()` (step 0 of the transition), before any cleanup runs. It
captures:
- `attendance_rate` (Float) and `attendance_issue_count` (Integer) - **aggregate numbers only**.
- Per-subject grades (`subject_record_ids` → `internal_grade`/`external_grade`/`final_grade`/
  `attendance_rate`) and per-outcome scores (`outcome_record_ids` → `round1_score`/`round2_score`)
  - real detail, but only for **grades**, not attendance/notification detail.

**Currently DELETED (`unlink()`), all via `_ems_clear_operational_records()` unless noted:**
- `ems.enrollment` (also separately by group in `_apply_cleanup()` itself, unrelated call site)
- `ems.grade_outcome_line`
- `ems.grade_subject_line`
- `ems.attendance_session_line` (the per-student status row within a session)
- `ems.attendance_issue_student` / `ems.attendance_issue_tutor` (cascade + `remove_if_empty()`) -
  **only for a student actually leaving in `_scope_students()`** for this specific run
- `ems.grade_session` (by group, in `_apply_cleanup()` directly - unrelated to the per-student path)

**Currently ARCHIVED (`action_archive()`):**
- `ems.attendance_template` / `ems.attendance_schedule` / `ems.attendance_session_header`
- `resource.calendar` / `resource.calendar.attendance`
- `ems.attendance_justification` (this session's own new code) - **never deleted anywhere in the
  codebase**, confirmed by grep
- `ems.attendance_issue_status` / `_student` / `_tutor`, **for the case OUTSIDE `_scope_students()`**
  (this session's own new code - e.g. a student already stranded, main_group_id already cleared)

**The asymmetry worth resolving:** the SAME two models (`attendance_issue_student`/`_tutor`) are
DELETED for a student in scope, but ARCHIVED for one outside it (a purely incidental difference in
which mechanism happens to reach them first, not a deliberate policy choice about the data itself).
Whichever is "right" should probably apply to both paths, not depend on which specific run finds
the record first.

# Open questions to resolve with Juan/the developer before changing anything

1. **Grade detail** (`ems.grade_outcome_line`/`ems.grade_subject_line`): `year_record` captures the
   FINAL grade per subject/outcome, but not necessarily every intermediate detail these live
   models might carry (check exactly what's lost vs. what `_apply_history()` actually copies -
   read `_apply_history()`'s own implementation before assuming either way).
2. **Attendance session line detail** (`ems.attendance_session_line`): `year_record` only keeps the
   aggregate `attendance_rate` - the per-session, per-status detail (which specific day, which
   status - attended/miss/justified) is genuinely lost on deletion, with nothing else preserving
   it. Confirm whether that's an accepted, deliberate trade-off (the docstring's own framing
   suggests yes: "the live records have nothing left to say") or whether it should move to
   archiving instead, now that this session has established an archiving path for the *adjacent*
   models (issues, justifications) referencing that exact same session data.
3. **Daily issue detail** (`ems.attendance_issue_student`/`_tutor`/`_status`): only the aggregate
   `attendance_issue_count` survives deletion - which specific date, which student, whether the
   notification was ever actually delivered (`notification_status`) is lost. Resolve the asymmetry
   above: pick ONE policy (delete or archive) and apply it to both the in-scope and out-of-scope
   path, rather than leaving it as an accident of which code path reaches the record first.
4. **Enrollment** (`ems.enrollment`): already deleted unconditionally today, both by student
   (leaving) and by group (transitioning) - confirm this one is genuinely fine as pure deletion
   (an enrollment is arguably pure "current state," not historical data at all - no case-by-case
   record of "which subjects was this student enrolled in on which specific date" seems needed
   once the year's grades are frozen), or whether even this deserves archiving for a different
   reason (audit trail of what was offered/taken, independent of the final grade).
5. **Grade session** (`ems.grade_session`, deleted by group): the existing comment in
   `_apply_cleanup()` explains WHY it must be deleted, not just archived - `UNIQUE(group_id,
   subject_id, round)` carries no course, so leaving an archived one behind would block creating
   next year's round 1 for the same group/subject. Confirm whether this is a genuine structural
   constraint (in which case deletion here is correct and not up for debate) or something a schema
   change (adding a course dimension to that uniqueness) could resolve if archiving turned out to
   be wanted instead - lower priority, since the current behavior has a real, working justification
   already, unlike the others above.

# Suggested approach when this gets picked up

1. Read `_apply_history()` (step 0) in full first - it's the thing that actually determines what's
   "already captured" for grades/attendance rate; don't assume from this plan's own summary above,
   verify against the current code.
2. For each model in the "currently deleted" list, get an explicit answer from Juan/the developer:
   is losing the per-record detail acceptable, given what `year_record` (or nothing) already keeps?
3. Resolve the `attendance_issue_student`/`_tutor` in-scope-vs-out-of-scope asymmetry explicitly -
   likely the single highest-value fix here, since it's an inconsistency with no real justification
   behind it (unlike grade_session's own genuine schema constraint).
4. Any change from delete→archive needs a migration for existing production data that was already
   deleted under the old behavior - there's nothing to migrate for those (they're gone), but new
   deletions going forward would stop once the code changes; no backfill possible for already-lost
   history.
5. Follow this repo's own TDD+DTON workflow for whatever change results - this plan is scoped to
   the *audit*, not to a decided fix.

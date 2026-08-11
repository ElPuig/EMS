# Fixes:

## Teachers created before 2026-07-12 could end up with no personal working-schedule calendar at all:
- `hr.employee.create()`'s auto-calendar creation only started with commit `bc29e04b` (18.0.0.20.0) - any teacher already in the database before that (or whose `employee_type` only became `'teacher'` later) could have `resource_calendar_id` empty. The working-schedule importer silently no-ops writing onto an empty calendar, leaving a teacher with real `ems.teaching` rows but an empty "Schedule" tab, with no error shown anywhere.
- Backfilled for both paths: a fresh install (`post_init_hook`) and an existing installation upgrading (`migrations/18.0.0.22.0/post-migrate.py`) now create a real personal calendar for every teacher still missing one, mirroring `create()`'s own logic exactly (shared via a new `hr.employee._ems_create_personal_calendar()` helper). Verified against this dev database: 7 real teachers backfilled.

# Internal changes:

## `resource.calendar.attendance` now carries a real FK to the `ems.attendance_schedule` line it represents:
- First phase of `plans/calendar_driven_attendance_templates.md` (point 4 only - the rest of that plan is still proposed, not implemented). Until now, the link between a teacher's weekly calendar block and the recurring class-session line it maps to was purely inferred by content matching (teacher + subject + group overlap + weekday/time) - fragile, and the exact class of bug fixed earlier this same branch (a stale room match silently breaking the link).
- New `resource.calendar.attendance.attendance_schedule_id` (Many2one) is captured automatically at the end of every schedule sync (`ems.attendance_template._link_calendar_attendance`, called from both `sync_from_schedule_batch` and `sync_from_schedule_batch_fresh_import`) - both the live "Schedule" tab edits and the XML batch importer. Correctly handles co-teaching (several teachers' own personal calendar rows all pointing at the same shared schedule line) and an untouched co-teacher whose slot survives a merge.
- Deliberately no historical backfill: rows written before this change keep the field empty rather than re-running the same ambiguity-prone inference this FK exists to stop needing. `find_schedule_lines_for_teaching` (the old inference lookup) is unchanged and still the fallback for any pre-existing block - `course_transition_wizard` has not been switched over yet.

# Related with:
- Partial work on #372 (point 4 of the plan only - moving `student_ids`, locking direct template creation/archival, and the uniqueness constraint are still pending, to be tackled as separate follow-up phases).

# Extend archive-or-delete to course_transition_wizard's own template archival

**Status: partially resolved as a side effect of the bottom-up sync redesign's Phase 7
(2026-09-08) - see below. The remaining item is still current, not started.**

## Context

`ems.attendance_template._archive_or_delete()` (added 2026-09-07, see
`docs/en/developers/attendance/attendance_template.md`'s "Archive-or-delete" section) deletes a
superseded/duplicate template outright instead of archiving it forever, but only when none of its
schedule lines (active or archived) ever had a real `attendance_session_ids` entry. Applied so far
to every template-level archival call site in the calendar-sync pipeline (`_sync_from_schedule_batch`,
`_archive_stale_schedule_sync`, `_regenerate_all_from_calendars`) and to the working-schedule import
wizard's own `db_conflicts` "prevail_left" resolution (`working_schedule.py`).

## What's left

Originally, `models/settings/course_transition_wizard.py` had two more template-level
`action_archive()` call sites deliberately left untouched by the pass that introduced
`_archive_or_delete()`:

- ~~The departing-co-teacher correction (`_apply_calendar_archival()`'s own `still_needed`/
  `departures_by_template` decision, then archiving via a bare `action_archive()` when no teacher
  remained): when no remaining teacher still needs a template after some teachers leave, it
  archived the template outright.~~ **Resolved as a side effect, not a deliberate fix** - the
  bottom-up sync redesign's Phase 7 (2026-09-08) deleted this entire hand-rolled decision and
  replaced it with the automatic calendar-sync hook, which already routes every template-level
  archival it decides through `_archive_or_delete()` (it's the same call site this plan's own
  first paragraph already lists as converted: `_archive_stale_schedule_sync`). See
  `docs/en/developers/settings/course_transition_wizard.md`'s "Teacher calendar blocks" section.
- `_templates_to_archive()`'s own end-of-course archival (study-scoped, still a bare
  `action_archive()`): every template belonging to a study transitioning to the next course. This
  is the one remaining item - a genuinely different, deliberately-kept-as-is rule (not
  calendar-driven, so untouched by the Phase 7 redesign above).

Same shape as the call sites already converted - switching this one to `_archive_or_delete()`
would very likely be a small, mechanical change. Not done yet because course transition is
explicitly `IRREVERSIBLE` (own docstring) and has a much larger test surface (`TestCourseTransition`,
124 tests as of 2026-09-08) - worth doing as its own deliberate pass with the developer's go-ahead,
not folded silently into an unrelated fix.

## Next steps if picked up

1. Confirm with the developer whether this scope expansion is wanted.
2. Swap the one remaining call site (`_templates_to_archive()`'s own `action_archive()` in
   `_apply_cleanup()`) to `_archive_or_delete()`.
3. Audit `TestCourseTransition` for any assertion on `.active`/existence of a template that would
   now be deleted instead of archived (same pattern already hit in
   `tests/test_working_schedules_import_wizard.py` and `tests/test_attendance_template.py` for the
   sync-pipeline call sites - grep `assertFalse(.*\.active)` / `assertTrue(.*\.active)` scoped to
   template records, not schedule lines).
4. Run `./test.sh TestCourseTransition` (124 tests as of 2026-09-08) to confirm.
5. Fold into the same migration (or a follow-up one) that cleans up the existing archived-unused
   backlog, so production doesn't need two separate cleanup passes.

Status: PARTIALLY IMPLEMENTED 2026-08-01, same session as the design was confirmed. Supersedes
the deleted `plans/group_room_per_subject_override.md` (that problem is solved here by rule 2
below instead of a separate fix).

**Done:** #1 (scoped per-employee file import removed - `teacher_id`/`file` fields, `_onchange_file`,
the Schedule tab's "Import" button) and #2 (`find_external_conflicts` → `classify_external_conflicts`,
co-teaching left alone + surfaced non-blocking, space conflicts now block instead of auto-archiving).
Verified: backend tests (`TestWorkingSchedulesImportWizard`, `TestAttendanceTemplate`), the wizard's
own browser tour, and `TestEmployeeTour` (Schedule tab still renders without the Import button) all
green; docs/i18n/changelog updated.

**Not done:** #3, the group/teacher correction dropdown for unresolved codes - a separate, sizable
UI feature (new child transient model(s), editable list view, re-triggering the onchange chain).
Check with the developer before starting this piece.

# Why

The current importer (`ems.working_schedules_import_wizard` + `ems.attendance_template`'s
`sync_from_schedule_batch`/`_reconcile_teacher_groups`/`find_external_conflicts`) assumes it may
be writing on top of an already-populated, still-current schedule — so it tries to reconcile
co-teaching, split/merge templates, and auto-archive "external" conflicts by guessing. That
machinery is genuinely complex, and a real bug report (2026-08-01, an overlap `ValidationError`
during a batch import that couldn't be reproduced against current data - see this session's
investigation) showed how hard it is to reason about.

**Key fact that unlocks the simplification** (confirmed by reading
`models/settings/course_transition_wizard.py`, merged in from
`353-add-course-transition-wizard-setup-next-course` same session): `ems.group` records are
**permanent and reused across academic years** ("ems.group carries the course number but not the
academic year, so groups are reused" - `_apply_detach_unplaced`'s own docstring). What actually
gets archived at transition time is each outgoing `ems.attendance_template` (`_apply_cleanup`,
scoped to the studies being transitioned in that run - transitions happen per-study/department,
not all at once). So the moment a study's transition has been applied, every schedule import for
its groups starts from a genuinely blank slate — no reconciliation-against-existing-data is
needed, because there IS no existing active data to reconcile against for that scope.

This means the importer doesn't need to know or care whether it's "next-course prep" or not: it
can always assume it's filling empty slots, and treat any ACTIVE overlap it finds as a real
problem to resolve interactively, never something to guess-and-archive.

# What changes

## 1. Batch import only, no more mid-course single-teacher file import

Remove the scoped path entirely: `ems.working_schedules_import_wizard.file` field,
`teacher_id` field, `_onchange_file`, the `item.get('teacher_id')` branch in `create()`, and the
"Import" button + `onImportClick()` on the employee's own Schedule tab
(`static/src/js/backend/schedule_grid_field.js`). A teacher joining mid-year gets their schedule
via the tab's own **existing** "New" panel (`openNewPanel()` - blank framework or copy from
another teacher, already built, untouched) or by hand - never a single-file XML upload.

Keeps `attachment_ids` (the general, cog-menu importer) as the only way in. Keeps the
pending-identification-code mechanism (`X1`, `X2`...) - a batch load can still include posts not
yet staffed.

## 2. Batch sync stops reconciling against existing data - new simpler write path

`sync_from_schedule_batch`/`_reconcile_teacher_groups`/`find_external_conflicts` stay **exactly
as they are today**, untouched - they are also used by `ems.teaching.sync_from_schedule()` for
the Schedule tab's own live, single-teacher edit, which is a genuinely different case (editing an
already-populated schedule mid-year) the developer explicitly wants unchanged.

The batch file importer gets a **new**, separate write path (name TBD while implementing, e.g.
`sync_from_schedule_batch_fresh`) that:
- Parses every teacher node's entries as today.
- Checks for overlaps **within the batch itself** (two entries from this same import landing on
  the same day/time/space) AND against **any currently active** `ems.attendance_schedule`
  (regardless of which course it belongs to - there is no "course" field on the schedule models
  to filter by, and none is needed: an active line that collides is a real problem either way).
- Classifies each overlap found using the developer's three rules instead of silently archiving
  anything:
  1. **Same subject + same group + same space** → likely co-teaching. Non-blocking, ask for
     confirmation (default: yes, it's co-teaching) - matches `is_co_teaching_with`'s existing
     definition, reused here.
  2. **Different group (same or different subject) + same space** → the two bookings can't both
     be right. Ask which space to keep it in (default: the space that's already free / whichever
     one caused the problem - exact UX TBD while implementing).
  3. **Same subject + same group + different space** → contradiction, always a blocking error
     (the same class can't be in two rooms) - fix the subject or the group in the source file.
- Never auto-archives anything the user hasn't confirmed.

## 3. Interactive correction for unresolved group/teacher

Today an unresolved group acronym or teacher e-mail either blocks the import (general path) or
raises (create()). New behavior: when the onchange can't resolve a `<Students>` group name or a
teacher e-mail, list it with a dropdown (Many2one selection, in the wizard's own preview area) so
the admin can pick the right one right there, instead of having to go fix the source file and
re-upload. Once picked, the resolved id feeds back into the same parsing the rest of the wizard
already does.

# Not changing

- `ems.teaching.sync_from_schedule()`, `sync_from_schedule_batch`, `_reconcile_teacher_groups`,
  `find_external_conflicts`, `_archive_stale_schedule_sync`, `_write_schedule_sync` - all stay,
  serving the Schedule tab's own live single-teacher edit exactly as today.
- `ems.attendance_schedule.check_overlap` (the `@api.constrains`) - still the actual DB-level
  guardrail; the new interactive resolution above is a *pre-check* in the wizard so the user gets
  asked instead of hitting that constraint's raw error, not a replacement for it.
- Pending-identification-code (`X1`/`X2`) creation logic in `create()`.
- The Schedule tab's own "New" panel (blank framework / copy from another teacher) - already the
  intended mechanism for a mid-year newcomer.

# Rough shape of the work (DTON)

1. **D:** update `docs/en/developers/employees/working_schedule.md` with the new design (this
   plan's content, condensed) once implemented; user-facing admin doc
   (`docs/{en,ca,es}/secretary/` or wherever this wizard is documented for the acting role) needs
   the "no more per-teacher file import, use New/copy instead" + "you'll be asked how to resolve a
   clash" behavior change explained.
2. **T (Red):** tests for: batch-only (scoped path removed - old scoped tests deleted/ported),
   the three overlap rules (co-teaching confirm, space-conflict choice, same-group-different-space
   error), group/teacher correction dropdowns, pending-code path untouched. Tour coverage for the
   new interactive bits (confirmation, dropdowns) - these are exactly the kind of client-side
   behavior a clean `./upgrade.sh` can't verify.
3. **T (Green):** implement.
4. **N:** coding-guidelines pass, pylint redefined-builtin check.
5. **Close:** i18n (new banners/labels), changelog, delete this plan file.

# Open design questions to settle while implementing (not blocking, use best judgment - flag if
genuinely unclear)

- Exact wording/UX for rule 2's "which space do you want" choice - a dropdown of the two
  candidate spaces, or something else.
- Whether the group/teacher correction dropdown lives inline per unresolved item, or as a
  separate resolution step/dialog.

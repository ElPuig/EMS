Status: **code + tests implemented and green (2026-09-01)** — the design below (calendar-driven
`ems.teaching` resync, `ems.teaching.unlink()` clearing a stale `tutor_id`, `_ems_clear_stale_
delegate()` reused for the stranded-student path) is now in `models/employees/teaching.py`,
`models/employees/employee.py`, `models/attendance/attendance_template.py`,
`models/settings/course_transition_wizard.py`, `models/contacts/contact.py` and
`models/employees/working_schedule.py` (the sibling Guard Duty Board calendar-cascade fix). Dev
docs updated to match (`docs/en/developers/{employees/teaching,employees/working_schedule,
settings/course_transition_wizard,contacts/group,attendance/guard_duty_board}.md`).
**Still outstanding: the one-time migration for already-existing ghost data** (see "Migration —
drafted, not yet created" below) — needs the developer's go-ahead on the manifest version bump
before the `migrations/<version>/` folder can be created, per this repo's own rule. Delete this
file once that migration ships and is verified.

**Developer correction (2026-09-01, same day):** groups must NOT be auto-archived — see
"Developer feedback" section near the bottom, which supersedes the "auto-archive an emptied
group" idea floated in the diagnosis below. The diagnosis itself (what's broken) still stands;
only the "suggested approach" changed as a result.

# Origin

Developer report (2026-09-01, branch `384-guard-duty-schedule-incorrect-data`): archived/
transferred teachers (e.g. Priscila Rodríguez) still appear on the Guard Duty Board. That
investigation (see `project_guard_duty_board_stale_calendar_rows` in memory) found a first gap
in `_apply_calendar_rollover()`. While reporting that, the developer flagged a second, related
suspicion in the same area: after a course transition, "teachings" (`ems.teaching`) don't get
cleaned up and departed/reassigned teachers keep showing as group tutors. Confirmed empirically
below — this is real, and larger in scope than the guard-duty gap.

# Root cause

`course_transition_wizard.py`'s cleanup (`_apply_calendar_archival`/`_apply_calendar_rollover`,
`_apply_cleanup`, `_ems_clear_operational_records`, etc.) is thorough for `resource.calendar`/
`resource.calendar.attendance`, templates, schedules, sessions, justifications and issues — but
**never touches `ems.group` (`tutor_id`, `active`) or `ems.teaching` at all.** `_apply_detach_
unplaced()` (line ~700) clears a stranded student's `main_group_id` when no placement target
exists (e.g. the last cohort of a finishing 2-year cycle), which can leave a group with **zero**
active students — but nothing downstream reacts to that:

1. **`ems.group.tutor_id` stays set** — the "Tutor" role/badge on `hr.employee` is a *stored*
   field (`role_ids`), only ever recomputed reactively by `_sync_tutor_role()` when `tutor_id`
   itself is written (`group.py` `write()`/`create()`). Emptying the group via `main_group_id`
   never touches `tutor_id`, so `_sync_tutor_role()` never fires and the role sticks forever.
2. **`ems.group.active` stays `True`** — the group is never archived even though its help text
   explicitly describes this exact case ("a group that won't be used this course... should be
   archived instead of deleted").
3. **`ems.teaching` rows for that group are never touched** — this model is only synced by
   `EmsTeaching.sync_from_schedule()`, called from two places: the employee Schedule tab's grid
   widget (`replace=True`, treats the given entries as the WHOLE truth) and the working-schedule
   XML importer (`replace=False`, additive only, by design — see its own docstring). Course
   transition calls neither, so a teacher's teaching links from the outgoing course survive
   untouched. This matches the developer's own manual test: resetting a teacher's calendar to a
   framework via the Schedule tab (`replace=True`) *does* clean `ems.teaching` (confirms the
   sync mechanism itself works) — but that's an incidental side effect of a manual, per-teacher
   schedule edit, not something the transition itself does, and it does nothing for `tutor_id`
   (an entirely separate field/relation `sync_from_schedule` never touches).

`ems.teaching` isn't cosmetic — it backs real logic: the "canonical teacher" lookup for a
(group, subject) in `grade_session.py`, group/subject scoping in `attendance_reports.py`, and
participant resolution in `limesurvey.py`. A stale row is a latent-wrong-teacher risk, not just
a UI nuisance.

# Confirmed in this dev DB (`ems`), 2026-09-01, after the 2026-08-07 course transition (2025-2026 → 2026-2027)

- **97 active `ems.teaching` rows** across **31 distinct teachers**, all pointing at **10 main
  groups** with zero currently-active students (`AD1B`, `AIF1B`, `AIF2B`, `AO1A`, `DEV1A`,
  `GA1D`, `GA2B`, `GA2D`, `SA1A`, `SA2A` — mostly the finishing 2nd year of 2-year cycles).
- **6 employees still tagged/shown as "Tutor"** of one of those same empty, still-`active=True`
  groups: Carlos Albert (AIF1B), Eric Bautista (AIF2B), Gabriel Manrubia (DEV1A), Laura Pastor
  (AO1A), Marina Bolós Pozuelo (SA1A), Marta Martínez (GA2B).
- None of the 10 groups have been archived; `tutor_id` is untouched on every one that had it set.

# Relationship to the guard-duty-board gap (same report, different layer)

Both bugs share one architectural cause: **the course transition wizard archives the CALENDAR
side of a teacher's outgoing assignments reasonably well, but nothing cleans up the adjacent,
loosely-coupled models that mirror the same real-world fact** (which subject/group a teacher
teaches, who tutors which group, which non-teaching commitments a teacher still has). Fixing
them together makes sense — they're the same missing step at three different layers:
- `resource.calendar.attendance` (non-teaching rows) — see the guard-duty-board diagnosis.
- `ems.teaching` — this file.
- `ems.group.tutor_id`/`.active` — this file.

# Developer feedback (2026-09-01) — supersedes the group-archival idea above

- **Groups must never be auto-archived by the transition.** They're deliberately reusable
  entities (`ems.group.course` is "which year of the study", not a school-year FK — there is no
  `ems.course` relation on `ems.group` at all; the same "AIF1B" row is meant to come back for a
  future cohort of that same cycle/year). The "auto-archive an emptied group" idea in the
  diagnosis above is explicitly rejected — do not revisit it without new developer direction.
- **The right trigger point is the CALENDAR/TEMPLATE archival that already exists and already
  works**, not "group has 0 students": *"Archivar sus resource.calendar.attendance implica el
  archivado de sus attendance_template. Eso también debería archivar el teaching relacionado."*
  Confirmed by reading `attendance_template.py`: `EmsAttendanceTemplate.action_archive()` (line
  188) already cascades `self.attendance_schedule_ids.action_archive()`, and course transition's
  own `_apply_calendar_archival()` already archives the right templates via `_templates_to_
  archive()`/`departures_by_template` — this part of the pipeline is already correct and tested
  (`project_course_transition_teacher_schedule_archival_plan`, ✅ done 2026-08-06). `ems.teaching`
  is the one model this existing, working cascade never reaches.
- **`ems.teaching` has no direct relation to `attendance_template`/`attendance_schedule` today**
  (confirmed: `teaching.py` has a bare `# TODO: course_id should be added!`, no FK at all) — the
  developer asked to decide whether to add one or to look it up, whichever is more efficient.

## Analysis: don't add a stored relation — resync `ems.teaching` from the calendar directly, like `ems.attendance_template` already does

**Recommendation: no new FK.** Reasons, from reading `attendance_template.py`/`working_schedule.py`
in full:

1. **`ems.teaching` and `ems.attendance_template` are already two independent, parallel
   consumers of the exact same input**, not one derived from the other. `working_schedule.py:117-118`
   (the Schedule tab's live single-teacher edit) already calls
   `ems.teaching.sync_from_schedule(teacher, entries)` **and**
   `ems.attendance_template.sync_from_schedule(teacher, entries, ...)` side by side, both fed the
   *same* `entries` list built from the calendar grid — this is exactly why the developer's own
   manual test (resetting a teacher to a framework) already correctly cleans `ems.teaching`: it's
   not because it's linked to the template, it's because both are synced from the same source at
   the same time.
2. **Hooking a fix into `EmsAttendanceTemplate.action_archive()` itself is a trap.** A template
   only reaches `action_archive()` when it's being fully superseded — but course transition's
   (and the schedule sync's own) archive step always runs as a **two-pass batch**: archive every
   stale/superseded template first, across the whole batch, *then* write/create the replacement
   templates (`sync_from_schedule_batch`'s own docstring explains why: avoiding false
   `check_overlap` collisions). If `ems.teaching` cleanup fired reactively inside
   `action_archive()`, it would run *before* the replacement templates exist yet — e.g. a
   co-teaching split (`{A,B}` together → `{A}` solo + `{B}` solo) archives the old combined
   template first; a teacher who's still validly teaching group A moments later would have their
   still-valid `ems.teaching` row wiped by the premature archive-time hook, then need to be
   silently recreated by the write pass — fragile, and only correct by accident of ordering.
3. **`ems.attendance_template` already has a proven pattern for exactly this kind of full resync**:
   `regenerate_all_from_calendars()` (line 238) archives every active template for a set of
   teachers and rebuilds a fresh, correct set straight from each teacher's *current*
   `resource_calendar_id.attendance_ids` — calendar as the single source of truth, no
   intermediate relation needed. **The same idea, applied to `ems.teaching`, needs no new field
   at all**: build the same `{'subject_id', 'group_ids'}` entries dict `regenerate_all_from_
   calendars()` already builds (reusable as-is — same shape `ems.teaching.sync_from_schedule`
   already expects), and call `ems.teaching.sync_from_schedule(teacher, entries)` (default
   `replace=True`) once the teacher's calendar is in its final state for the transition. This is
   the "buscarlo" option, and it's both simpler and more robust than "relacionarlo" — no FK to
   keep in sync as templates get archived/recreated/split over time, and it reuses a method that
   already exists and is already exercised for templates.
4. **Where exactly to call it** (needs developer confirmation, see questions asked in chat): the
   natural point is once per course-transition run, for exactly the `affected_teachers` recordset
   `_apply_calendar_archival()` already computes and returns (currently only fed to
   `_apply_calendar_rollover`) — at that point each teacher's `resource_calendar_id` (rolled over
   to a fresh calendar, or partially archived in place) already reflects the FINAL truth for this
   transition, so reading straight off it and calling `sync_from_schedule(teacher, entries)`
   naturally drops exactly the stale (subject, group) combos and keeps the still-valid ones — no
   group-emptiness heuristic needed, no group archival needed. **Important corollary this
   surfaces**: `regenerate_all_from_calendars()` itself (the template-side migration utility) has
   this *exact same* gap — it never touches `ems.teaching` either — worth confirming whether that
   utility should also gain the same call, since it's the other existing place templates get
   force-resynced from the calendar wholesale.

## Still open: `ems.group.tutor_id`/`delegate_id`

The developer's message didn't address this part of the original report. Groups themselves
won't be archived, but the STUDENTS they used to hold are gone (detached, not archived, via
`_apply_detach_unplaced`) — so `tutor_id`/`delegate_id` pointing at last year's tutor for a now-
empty group is still presumably wrong, independent of whether the group record itself survives
for reuse. Needs an explicit developer decision: clear `tutor_id`/`delegate_id` (plain `write()`,
so `_sync_tutor_role()` fires exactly like any manual reassignment) when a group transitions to
zero active students, or leave it untouched until someone manually reassigns the group next time
it's used? See questions asked in chat before implementing either way.

# Suggested approach when this gets picked up

**All resolved and implemented 2026-09-01** (developer confirmed all three design questions in
chat): trigger point is both `_apply_teaching_resync()` (course transition) and
`regenerate_all_from_calendars()`; `tutor_id` is derived from the tutorship `ems.teaching` row
via `unlink()`, `delegate_id` reuses `_ems_clear_stale_delegate()`. Only the migration below is
still pending.

# Migration — drafted, not yet created (needs developer go-ahead on the version number)

Current manifest version is `18.0.0.23.0`, **already tagged/released** (`git tag` shows
`v18.0.0.23.0`) — this migration needs a NEW version folder, proposed to the developer rather
than assumed, per CLAUDE.md's "Never bump the manifest version yourself" rule.

Per the developer's explicit instruction (2026-09-01): *"la migración deberá tener en cuenta
[...] debe buscar registros y arreglarlos, nunca asumir en función de lo que hay en esta bbdd de
desarrollo"* — every step below re-derives correctness from live, current state (calendar
contents, actual group membership, actual matching `ems.teaching` rows), never from this dev DB's
own specific counts (97 teachings / 6 tutors / 387 leftover calendar rows) — those numbers are
illustrative only, not what the migration targets. Idempotent and safe to run against a
production database that the developer has already partially hand-fixed: every step is a
"reconcile against current truth" operation that no-ops wherever things are already correct.

Belongs in **`post-migrate.py`** (a pure data reconciliation, not a rename, and not gated by any
new column - see CLAUDE.md's pre vs. post rule; matches the `_backfill_default_schedule_
framework`/`_enable_unaccent_extension` precedent for one-time backfills).

```python
def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # 1) Archive any resource.calendar.attendance row still active=True on an already-archived
    #    calendar - exactly what ems_working_schedule.action_archive()'s new cascade would
    #    already have done, applied retroactively to state that predates it.
    cr.execute("""
        UPDATE resource_calendar_attendance rca
        SET active = false
        FROM resource_calendar rc
        WHERE rca.calendar_id = rc.id AND rc.active = false AND rca.active = true
    """)

    # 2) Resync ems.teaching from each teacher's CURRENT calendar - reuses the exact same fix
    #    (hr.employee._teaching_entries_from_calendar() + ems.teaching.sync_from_schedule()),
    #    so every teacher's teaching links are re-derived from what their calendar actually
    #    says right now, not assumed. Safe/idempotent for a teacher already in sync (no net
    #    change - see test_ems_teaching_sync.py::test_keeps_unchanged_teaching_record). Also
    #    what clears a stale tutor_id wherever the tutorship ems.teaching row itself goes away
    #    (ems.teaching.unlink()'s own hook) - no separate tutor pass needed for that case.
    teachers = env['hr.employee'].search([
        ('employee_type', '=', 'teacher'),
        ('resource_calendar_id', '!=', False),
        ('resource_calendar_id.is_framework', '=', False),
    ])
    for teacher in teachers:
        env['ems.teaching'].sync_from_schedule(teacher, teacher._teaching_entries_from_calendar())

    # 3) Defensive tutor_id backfill: catches a tutor_id set by hand on the group form with no
    #    matching calendar/TUT-teaching row to begin with, so step 2's unlink() hook never had
    #    anything to react to. Searches live state (is there STILL a matching active tutorship
    #    teaching for this exact group+teacher, right now) rather than assuming.
    groups = env['ems.group'].search([('tutor_id', '!=', False)])
    for group in groups:
        has_tutorship_teaching = env['ems.teaching'].search_count([
            ('teacher_id', '=', group.tutor_id.id), ('group_id', '=', group.id),
            ('subject_id.is_tutorship', '=', True), ('active', '=', True),
        ])
        if not has_tutorship_teaching:
            group.tutor_id = False

    # 4) delegate_id backfill: clears it wherever the current delegate is no longer actually a
    #    member of the group - same check '_ems_clear_stale_delegate()' applies going forward.
    for group in env['ems.group'].search([('delegate_id', '!=', False)]):
        if group.delegate_id.main_group_id != group:
            group.delegate_id = False
```

Before creating `migrations/<version>/post-migrate.py` with this content: propose the next
version number to the developer and wait for their go-ahead (per CLAUDE.md), then run it locally
against this dev DB's actual pre-migration state and verify with `./upgrade.sh` before considering
it done - same empirical-verification standard as every other migration in this repo.

Status: Phases 1, 2 and (functionally) 3 implemented and tested (2026-09-02). What unblocked
Phase 2 - the developer's own answer, once actually asked with concrete examples, was that the
"blind wipe" WAS a real, separate bug (not the intended design after all - see Phase 2's own
section for the full back-and-forth) - the real feature that resulted, letting the admin choose
`import_mode` (`combine`/`replace`) on the working-schedule import wizard, is bigger than the
original mechanical "collapse two methods" idea, but delivers the same underlying unification and
then some. Phase 4 is still analysis/design only, not started, and still not recommended as a
full collapse - see its own section, unaffected by the rest of this update. Re-verify against the
code before picking up Phase 4, since `attendance_template.py`/`working_schedule.py`/
`course_transition_wizard.py` may have changed since this was written.

# Origin

Developer request (2026-09-02, branch `384-guard-duty-schedule-incorrect-data`, right after
`plans/course_transition_stale_teacher_assignments.md`'s fix landed): review the whole course
transition / working-schedule import / manual schedule editing system for simplification, on the
explicit intuition that `resource.calendar` should be the one top-level source of truth, with
`resource.calendar.attendance` derived from it and `ems.attendance_template`
(+ `ems.attendance_schedule`) and `ems.teaching` derived from *that* — so a manual calendar edit,
a course transition, or a schedule import all flow through the same downstream logic instead of
each reinventing it.

Turns out this is not a new idea for this codebase — `plans/calendar_driven_attendance_templates.md`
(GitHub issue #372, marked "✅ COMPLETE" 2026-08-11, still present in the repo even though its own
status line says it can be deleted once merged) already did exactly this for
`ems.attendance_template`/`ems.attendance_schedule`. `ems.teaching` was simply never brought into
that same design, and one piece of what #372 *did* build (the `attendance_schedule_id` FK) was
never wired into every place that could use it. This plan is about finishing that direction
consistently, not inventing a new one.

# Current state (as of 2026-09-02, before Phase 1): three write paths, four different sync mechanisms

Every one of these three paths correctly writes `resource.calendar.attendance` first (solid, not
part of what needs to change), but each then keeps `ems.attendance_template`/`ems.teaching` in
sync using a *different* mechanism:

1. **Manual edit** — `ems_working_schedule.apply_schedule_changes()`
   (`models/employees/working_schedule.py:101-118`). Writes the calendar from `cells`, then calls
   `ems.teaching.sync_from_schedule(teacher, entries)` **and**
   `ems.attendance_template.sync_from_schedule(teacher, entries, ...)` side by side — both fed the
   *same* `entries` derived from `cells`, not read back from the calendar just written.
2. **Working-schedule XML import** — `ems.working_schedules_import_wizard._apply_import()`
   (`working_schedule.py:1531-1612`). Per teacher: writes the calendar additively
   (`_write_teacher_schedule`, append-only — a file is only ever one slice), calls
   `ems.teaching.sync_from_schedule(teacher, entries, replace=False)`. Then, batched across every
   teacher at the end: `ems.attendance_template.sync_from_schedule_batch_fresh_import(teacher_entries)`.
   Again, both teaching and template syncs are fed the parsed XML entries, not the calendar.
3. **Course transition** — `course_transition_wizard.py`. Archives migrating calendar *blocks*
   (`_apply_calendar_archival`, `~line 731`); until Phase 1 (below), found which
   `ems.attendance_schedule` line a block backs via content-matching inference
   (`find_schedule_lines_for_teaching`) instead of the FK that already existed for this. Rolls
   calendars over (`_apply_calendar_rollover`). `_apply_teaching_resync()` (added 2026-09-01) reads
   straight from `teacher._teaching_entries_from_calendar()` — the one place that already
   implemented "read the calendar, derive the rest" for a normal (non-migration) write path.
4. **`ems.attendance_template.regenerate_all_from_calendars()`** (`models/attendance/
   attendance_template.py:238-323`) — the #372-built utility. Reads every teacher's calendar
   directly, archives everything, rebuilds both templates *and* (since 2026-09-01) `ems.teaching`
   from scratch. The "correct" calendar-as-source-of-truth pattern in its heaviest form — but only
   ever invoked from a one-time migration, never from the 3 live write paths above.

`ems.teaching` itself has **no FK to anything** — `models/employees/teaching.py` still carries a
bare `# TODO: course_id should be added!`, unlike `resource.calendar.attendance`, which got its
`attendance_schedule_id` FK in #372.

# Concrete redundancy/inconsistency found

- **`EmsAttendanceTemplate._reconcile_teacher_groups()` (live edit) vs. `_reconcile_fresh_import()`
  (import)** — `attendance_template.py:482-575` and `:577-664` — ~90 near-identical lines each,
  differing only in the "also reconsider every other active template a submitting teacher already
  owns" pre-scan step (needed for live-edit's "this call = the whole truth" semantics, wrong for
  import's "this file = one slice" semantics).
- ~~`_apply_calendar_archival()` still doesn't use the FK #372 built for exactly this purpose.~~
  **Fixed by Phase 1, see below.**
- **`ems.teaching` still isn't locked down the way `ems.attendance_template` is.** `security/
  ir.model.access.csv`: `ems.attendance_template` is `1,1,0,0` (create/unlink revoked, admin
  included — #372 point 3) vs. `ems.teaching` still `1,1,1,1` for admin (`ems_teaching_admin`
  line) — a direct manual create/unlink of a teaching row bypassing the calendar is still possible
  today, the exact gap #372 closed for templates.
- **Three separate places build the same `{'subject_id', 'group_ids', 'dayofweek', 'hour_from',
  'hour_to', 'space_id', 'date_from', 'date_to'}` entry-dict shape** from a calendar row: `hr.
  employee._teaching_entries_from_calendar()` (added 2026-09-01), the same helper now reused by
  `regenerate_all_from_calendars()`, and `apply_schedule_changes()`'s own `cells`-filtering. Not
  all currently share one implementation.

# Phase 1 — DONE, 2026-09-02: wire the existing FK into `_apply_calendar_archival()`

Replaced the `find_schedule_lines_for_teaching()` inference call with a direct read of
`block.attendance_schedule_id`, falling back to the inference lookup only when the FK is empty (a
legacy calendar row never resynced since 2026-08-11 — the expected, documented case per
`docs/en/developers/attendance/attendance_schedule.md`'s own note on this field, not an error).
See `models/settings/course_transition_wizard.py::_apply_calendar_archival`. Test:
`tests/test_course_transition.py::test_apply_finds_the_matching_line_via_the_attendance_schedule_id_fk`
(the other 9 pre-existing tests in that section all still exercise the fallback path, via the
`_calendar_block()` test helper which deliberately never sets the FK — unaffected, all still
pass). `./test.sh TestCourseTransition` (127 tests) and `./upgrade.sh` both clean.

# Phase 2 — DONE, 2026-09-02 (bigger than originally scoped: `import_mode` feature)

**First attempt (same day): reverted.** The original idea - replace `sync_from_schedule_batch` +
`sync_from_schedule_batch_fresh_import` with one calendar-reading method - broke a pre-existing
test the moment it was implemented, which led to finding a real bug in `_write_teacher_schedule`
(a leading `(5,)` unlink-all, wrong the moment two XML nodes resolve to the SAME real teacher
within one batch - fixed, kept) and then a second, bigger one: **the SAME `(5,)` mechanism also
silently wiped a teacher's calendar across SEPARATE wizard runs** - re-importing a shared/
reinforcement teacher in a later, unrelated file quietly erased everything an earlier import had
written. This was reported to the developer as a blocking question rather than guessed at, since
it directly re-litigated `_reconcile_fresh_import`'s own 2026-08-01 fix (built specifically to
protect this exact scenario at the template layer) - the first attempt reverted back to
`sync_from_schedule_batch_fresh_import`/`_reconcile_fresh_import` as they were, keeping only the
within-batch fix.

**Developer's answer, with a concrete worked example, changed the scope of the fix**: a later
import should be able to either REPLACE a teacher's calendar entirely (the original, apparently-
accidental default behavior, confirmed as sometimes genuinely wanted: *"si se quieren hacer
ajustes, se deben hacer a mano"*) or COMBINE with what an earlier import already wrote (needed for
the real Priscila-style shared-teacher scenario, confirmed with an "informática + administración"
example) - **the admin's own choice, per import**, with "lo nuevo prevalece" on any genuine slot
clash either way. This is a bigger feature than the original mechanical "collapse two methods"
plan, but it fixes the SAME underlying problem and, as a side effect, makes the original
unification safe again:

- New `ems_working_schedules_import_wizard.import_mode` field (`combine`/`replace`, default
  `combine`), chosen on the Welcome screen.
- `_write_teacher_schedule()` rewritten as a per-weekday-slot diff: any slot this batch describes
  always supersedes whatever was there before (both modes); `import_mode` only decides whether a
  slot this batch does NOT mention survives (`combine`) or also gets removed (`replace`). See its
  own docstring in `models/employees/working_schedule.py` for the exact algorithm.
- The existing "Existing schedule conflicts" screen (`_find_external_conflicts`'s own
  `self_candidates` branch, defaulting to "left prevails") turned out to already correctly resolve
  a genuine cross-import slot clash interactively, unchanged - it was the CALENDAR layer
  underneath it that was wrong, not the template-level resolution UI.
- With the calendar now trustworthy in both modes, the ORIGINAL Phase 2 goal was completed for
  real: `sync_from_schedule_batch_fresh_import`/`_reconcile_fresh_import` are deleted;
  `_apply_import()` now calls the same `sync_from_schedule_batch` the live Schedule-tab editor
  already used, fed each affected teacher's `_teaching_entries_from_calendar()`.
- Full test coverage: within-batch merge (calendar-level, not just template), combine preserving
  an unrelated earlier import, replace dropping it, two files uploaded together merging for a
  shared teacher (the literal scenario confirmed with the developer), plus a tour step confirming
  the new radio widget actually renders/works. `docs/en/developers/employees/working_schedule.md`'s
  own "Import wizard" section and `i18n/{ca,es}_ES.po` updated same cycle.

See the git history of this plan file for the full back-and-forth if the reasoning above is ever
worth revisiting - condensed here to the outcome and why, not every intermediate exchange.

# Phase 3 — DONE, 2026-09-02 (delivered as a side effect of Phase 2)

All three write paths now consistently resync `ems.teaching` from the calendar:
`apply_schedule_changes()` (manual edit) already did, unchanged; `_apply_import()` (working-
schedule import) now does, as part of Phase 2's own fix; `_apply_teaching_resync()`/
`regenerate_all_from_calendars()` (course transition / migration) already did (2026-09-01). No
separate "fold ems.teaching in" step was needed beyond what Phase 2 already required.

**Still open, a policy question, not a technical blocker:** lock `ems.teaching` down to
calendar-driven-only (revoke direct create/unlink in `ir.model.access.csv`, matching
`ems.attendance_template`'s own #372 lock) for full parity. Not done - purely a developer call on
whether direct manual create/unlink of a teaching row should stay possible at all, unrelated to
whether the sync itself is correct (it now is, regardless of this).

# Phase 4 — NOT STARTED, and likely not a full collapse: course transition's own template archival (higher risk)

The tempting end-state is "course transition just archives the migrating calendar blocks, then
calls the same Phase 2/3 resync for `affected_teachers`, and the resync figures out which
templates/teachings need archiving as a natural consequence." **This is probably not safely
achievable as a full replacement**: course transition operates at **study-scoped, partial-calendar
granularity** (only the blocks belonging to transitioning studies), while the unified resync
(Phase 2/3) is designed around "this is the teacher's *entire* current calendar, reconcile
everything to match it" — the same distinction that made `replace=True` vs `replace=False`
necessary in the first place, just one level up. Course transition's own archival logic also
encodes real, individually hard-won special cases with dedicated tests today (9 tests just for
`_apply_calendar_archival`): a departing co-teacher with real session history needs `_write_or_
new_version()`, not a raw `teacher_ids` write; a study genuinely out of scope must survive
untouched; an already-archived line with orphaned active sessions needs an unconditional,
unscoped catch-up. A generic "resync the whole teacher" call has no natural way to know which of a
teacher's several studies is "in scope for this specific transition run" — that scoping is the
actual irreducible complexity here, not an accident of the current implementation.

**Recommended scope for Phase 4, once 1-3 are done and stable:** keep `_apply_calendar_archival()`'s
own block-selection and study-scoping logic as-is (genuinely course-transition-specific domain
logic), but revisit whether any of its own template-side bookkeeping can now be simplified now
that Phase 1's FK-based lookup and a Phase 2/3 unified sync method exist to lean on — treat this
as a real re-evaluation once the groundwork lands, not a promised rewrite now.

# Verification approach for whichever phase gets picked up next

- `./test.sh TestCourseTransition`, `./test.sh` scoped to `TestAttendanceTemplate*`/
  `TestEmsTeachingSync`/`TestWorkingSchedule*`/`TestWorkingSchedulesImportWizard*` after each
  phase — these suites already exercise essentially every edge case this refactor touches.
- `./upgrade.sh` clean (no WARNING/ERROR/CRITICAL beyond the known inotify line) after each phase.
- A full, unscoped `./test.sh` only once, as the final gate for the whole effort (ask first) — not
  after every phase.
- `pylint --disable=all --enable=redefined-builtin` on every touched file.
- Realistic as its own multi-session effort (like #372 itself was), phase by phase with a
  dev-doc/changelog update per phase — not a single sitting.

# Explicitly out of scope

- Not re-litigating `calendar_driven_attendance_templates.md`'s point 4 discard (merging
  session/attendance machinery into the calendar model itself) — closed 2026-08-11 for a specific,
  still-valid reason (PAS staff have calendars but never teach).
- Cleanup of the now-stale `plans/calendar_driven_attendance_templates.md` file itself (marked
  "✅ COMPLETE," never deleted per its own stated convention) is a small, separate, low-risk
  housekeeping item worth doing regardless of which phases above get picked up.

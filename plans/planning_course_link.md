# Issue #503 — link `ems.planning` to an academic course

**Status: Phase 2 IMPLEMENTED 2026-09-23, verified stable across two consecutive `./upgrade.sh`
runs. Phases 3-4 designed, not yet implemented.** Phase 1 already landed (see "Overall issue
roadmap" below). If the planning/course/grading code changes significantly before phases 3-4 are
picked up, re-verify the details below before acting on them.

**Soft dependency: [[plans/current_course_auto_seed]] (v3, also implemented 2026-09-23).** Read
it first for why `res.company.current_course_id` needed fixing too — but note Phase 2's actual
design below does NOT hard-depend on it the way an earlier, abandoned version of this plan
assumed (see "Revision history" below): `ems.planning.course_id` no longer needs a real course to
exist at data-load time at all.

## Overall issue roadmap (context)

Issue #503 has 4 requirements, split into phases so the developer can review each one
separately:

1. **HOS/DHOS see every planning, not just their own — ✅ DONE (2026-09-22).** Access rules
   (`rule_planning_hos_all`/`rule_planning_outcome_hos_all`) + a "Show only mine" search filter
   (`is_own_subject`), same pattern as Communications. See
   `changelog/503-grade-correction-get-the-correct-course-planification-and-more.md`.
2. **Link `ems.planning` to `ems.course` — this plan.**
3. **Grade correction uses the correct year's planning — designed, small, depends on phase 2.**
4. **Manual final score override, Esfera-style — designed, independent of phases 2/3.**
5. Close (docs, i18n) — standard, after 2-4 land.

This file covers phase 2 in full, and restates phases 3-4's already-closed design for
continuity (nothing new there, just not yet implemented).

## Phase 2 — `ems.planning.course_id`

### Why

`ems.planning` (the internal/external grading ponderation per study+subject) has
`unique(study_id, subject_id)` — only ONE planning can ever exist for a given study+subject, for
the entire lifetime of the centre. `ems.study` is persistent (never recreated per year, only its
`transition_state` changes), so today a ponderation change affects every past and future course
retroactively. This is what makes grade correction on an old course pick up TODAY's ponderations
instead of the ones in force when that course actually ran (phase 3's bug).

### Model changes (`models/planning/planning.py`) — implemented

- New field: `course_id = fields.Many2one("ems.course", default=lambda self: self.env.company.current_course_id)`
  — **deliberately NOT `required=True`** at the field/DB level. Reasoning (found the hard way,
  see "Revision history"): a data-file-created row (the centre's own
  `data/custom/ccff/ems.planning-*.csv`) is created before `current_course_id` can be resolved on
  a fresh install (`post_init_hook`, which backfills it, runs strictly after all data has
  loaded) — a hard DB `NOT NULL` would break a clean install outright, and no placeholder record
  can safely stand in for it (see below). Required at the *application* level instead, via a new
  `check_course_id_required` `@api.constrains`, using the exact same `install_mode` escape hatch
  `check_ponderation` on this same model already relies on for the identical reason.
- `_sql_constraints`: `unique_study_subject` (`study_id, subject_id`) →
  `unique_study_subject_course` (`study_id, subject_id, course_id`).
- `_compute_name`: include the course when set, so two years' plannings for the same
  study+subject are distinguishable in list views (`"CFGS DAM2  Programació (2025-2026)"`);
  falls back to the course-less format while `course_id` is transiently empty right after a
  fresh install's data-file create. `TestPlanningLogic.test_compute_name`
  (`tests/test_planning.py`) needs updating for the course-inclusive format.
- `post_init_hook` (`__init__.py`): right after `_ems_seed_current_course()`
  ([[plans/current_course_auto_seed]]), backfill `course_id` onto any `ems.planning` still empty
  (the centre's own CSV rows) with the freshly-resolved current course.

### The centre's own seed data (`data/custom/ccff/ems.planning-*.csv`, 9 files) — unchanged

**No `course_id` column added.** An earlier version of this plan added one, pointing at a
placeholder course — reverted the same night once it turned out to actively break a second
consecutive upgrade (see [[plans/current_course_auto_seed]]'s "Revision history" and this file's
own, below). These rows simply get created with `course_id` empty, exactly like any other
`ems.planning` row would if the model's own `default=` can't resolve one yet, and `post_init_hook`
backfills them on a fresh install (see above). No manifest changes needed for this file group.

### Rollover at course transition (`models/settings/course_transition_wizard.py`) — implemented

`_apply_planning_rollover()`, called from `action_apply()`, scoped to `self.study_ids` (same
scoping every other `_apply_*` step in this wizard already uses, since studies transition at
different times):

```python
def _apply_planning_rollover(self):
    source = self.env['ems.planning'].search([
        ('study_id', 'in', self.study_ids.ids),
        ('course_id', '=', self.source_course_id.id),
    ])
    existing_keys = {
        (p.study_id.id, p.subject_id.id)
        for p in self.env['ems.planning'].search([
            ('study_id', 'in', self.study_ids.ids),
            ('course_id', '=', self.target_course_id.id),
        ])
    }
    for planning in source:
        if (planning.study_id.id, planning.subject_id.id) in existing_keys:
            continue
        planning.copy({'course_id': self.target_course_id.id})
```

**Correction, confirmed empirically 2026-09-23:** `copy()` does NOT duplicate
`planning_outcome_ids` on its own — a plain `one2many` field's `copy` attribute defaults to
`False` in this Odoo version (verified directly: `fields.One2many(...).copy` is `False` unless
explicitly set), the opposite of what an earlier version of this plan assumed. `_apply_planning_
rollover()` therefore rebuilds the outcome lines explicitly in the `copy()` call's own `default`
dict (`'planning_outcome_ids': [(0, 0, {...}) for outcome in planning.planning_outcome_ids]`),
same as the migration below does. Found the hard way: the wrong assumption first shipped
silently in the migration (masked by its own `install_mode=True` context, which also suppresses
`check_ponderation` - so empty outcome lines never raised anything there), and only surfaced as a
hard, loud failure in `course_transition_wizard`'s rollover (no such context), which is what
caught it before anything shipped. `name` (computed, `store=True`, no explicit `copy=True`) is
NOT copied and gets recomputed from `study_id`/`subject_id`/`course_id`, which ARE copied by
default (plain Many2one fields default to `copy=True`) - no manual handling needed there.

Idempotent by construction: relaunching a transition (or the same target course across two
separate runs) skips any study+subject that already has a target-course planning.

### Migration for THIS already-existing install (`migrations/18.0.0.28.0/post-migrate.py`) —
implemented

Three steps, in this order (`migrate()`):

1. `_drop_old_planning_unique_constraint(cr)` — raw SQL `DROP CONSTRAINT IF EXISTS
   ems_planning_unique_study_subject`. **Needed, confirmed empirically 2026-09-23**:
   `Registry.finalize_constraints()` only swaps a model's `_sql_constraints` for real at the very
   end of `load_modules()`, after every module's migrations have already run (same reasoning as
   `migrations/18.0.0.25.0/post-migrate.py`'s `_merge_duplicate_student_ids`) — the OLD
   `(study_id, subject_id)` constraint is still live throughout this whole script and blocks step
   3 from creating more than one planning per study+subject otherwise.
2. `_backfill_current_course_id(env)` — safety net shared in spirit with
   [[plans/current_course_auto_seed]]'s own backfill; a no-op on this DB.
3. `_replicate_plannings_across_history(env)`:
   ```python
   def _replicate_plannings_across_history(env):
       current = env.company.current_course_id
       if not current:
           return
       courses = env['ems.course'].search([('start', '<=', current.start)], order='start asc')
       if not courses:
           return
       plannings = env['ems.planning'].search([])
       for planning in plannings:
           planning.course_id = courses[0].id
           planning.flush_recordset(['course_id'])  # see note below - NOT optional
           for course in courses[1:]:
               planning.with_context(install_mode=True).copy({'course_id': course.id})
   ```
   Two non-obvious details, both confirmed empirically 2026-09-23 while implementing this:
   - **`flush_recordset(['course_id'])` is required, not defensive belt-and-braces.** Odoo's ORM
     batches a plain attribute write like `planning.course_id = courses[0].id` rather than
     flushing it to the DB immediately. Without the explicit flush, the `copy()` calls right
     after insert against the STILL-unflushed old `course_id` value, tripping the
     `(study_id, subject_id, course_id)` unique constraint against this very same row (reliably
     reproduced by removing the flush and re-running).
   - **`install_mode=True` on the `copy()` calls.** 5 pre-existing plannings (all "MP 1665:
     Digitalització aplicada als sectors productius", one per study: ASIX/DAM/DAW/AIF/AD) were
     found to already have outcome ponderations summing to 106%, not 100% — silently, since
     `check_ponderation` skips itself under `install_mode` (the context the original CSV load
     used) and the constraint has never fired since (only fires on create/write, never on a plain
     read). This migration's job is to replicate that already-live history unchanged, not to
     silently "fix" a centre curriculum percentage on the way through an unrelated migration —
     see [[plans/ems_planning_outcome_ponderation_over_100]] for the actual (still open) gap this
     surfaced, which needs the developer's own decision, not a migration script's guess.

On this dev DB (mirroring real production) this replicates every existing planning across
2024-2025, 2025-2026 and 2026-2027 (the current course) — not the not-yet-run 2027-2028/2028-2029,
which the rollover above will create for real once the centre actually transitions into them.
Verified stable: re-running `./upgrade.sh` a second time afterward does not duplicate or revert
anything (132 plannings × 3 courses = 396, unchanged across runs).

### Deleting `data/custom/ems.course.csv` — done

Confirmed safe (developer request, 2026-09-22): the 4 courses it seeds
(`__import__.ems_course_25_26` through `_28_29`) are `__import__`-owned. Per this project's own
documented `_process_end` mechanism (CLAUDE.md, "Data folder conventions"), a `module='__import__'`
record is never even a candidate for Odoo's data-file cleanup, regardless of whether the file that
originally declared it still exists. Deleting the file (and its manifest line) leaves the 4
already-created courses in this DB completely untouched, forever — verified via `./upgrade.sh`.
Nothing else in the codebase references these 4 specific xmlids outside already-applied
historical migration scripts (`migrations/18.0.0.8.0`, `18.0.0.22.0` — verified via grep).

### Tests — written and green

- `tests/test_planning.py` (`TestPlanningLogic`, 13 tests, all green): unique constraint permits
  two plannings for the same study+subject across different courses, still blocks a duplicate
  within the same course; `course_id` defaults to the current course; `check_course_id_required`
  raises outside `install_mode`, silent inside it; `_compute_name` handles both the course-set and
  transiently-course-less cases.
- `tests/test_course_transition.py` (`TestCourseTransition`, 126 tests, all green, including 2
  new ones): the target course gets one planning (matching ponderations AND outcome lines - this
  is exactly the case that caught the `copy=False` bug above) per source-course planning after
  `action_apply()`; relaunching the rollover directly is idempotent (no duplicate).
- No new tour needed for phase 2 alone — no new view surface (see phase 3/4 for where a tour
  does apply).

## Revision history (Phase 2 specifically)

- **2026-09-22/23, abandoned same night:** `course_id` was `required=True` at the DB level, with
  the centre's own `data/custom/ccff/ems.planning-*.csv` rows anchored to
  `ems.course_bootstrap` ([[plans/current_course_auto_seed]] v2's placeholder). Implemented,
  passed a first `./upgrade.sh`, then **failed on the second consecutive run**: the placeholder
  got silently recreated by that same upgrade's data reload (see the dependency plan's own
  revision history for the mechanism), and since these CSV rows synced `course_id` from the file
  on every load, that second run reverted all 132 already-migrated plannings back to the
  (newly-recreated) placeholder — undoing the whole migration. Root-caused and replaced the same
  night by making `course_id` non-required (this version), which removes the need for any
  placeholder at all.

## Phase 3 — grade correction uses the correct year's planning — IMPLEMENTED AND TESTED
2026-09-23

- `models/grades/grade_review_wizard.py::_fill_lines()` (`operation == 'add'` branch): added
  `('course_id', '=', self.record_id.course_id.id)` to the planning search domain.
- `models/grades/grade_session.py::_compute_planning_id()`: added
  `('course_id', '=', session.env.company.current_course_id.id)`.
- **Fixture gotcha found while writing the regression tests**: `tests/test_grade_review.py`'s
  existing `cls.planning3` fixture created its planning with NO explicit `course_id` (defaulting
  to whatever the current company course happened to be), while `cls.course` (the year_record's
  own course, used throughout that test class) is a separate, unrelated course (`2088-2089`).
  Before this phase, the unscoped search papered over the mismatch; with the course filter in
  place, the existing `test_add_a_missing_subject_from_its_teaching_plan` test would have failed
  outright had the fixture not been corrected to set `course_id: cls.course.id` explicitly - a
  good sign the fix is doing its job, not a regression to work around.
- **Regression tests, the actual point of this phase** (all green):
  `test_add_uses_the_planning_of_the_records_own_course_not_a_different_ones`
  (`tests/test_grade_review.py`, 27 tests total) and
  `test_planning_id_picks_the_current_course_not_a_different_ones`
  (`tests/test_grade_session.py`, 41 tests total) — each creates a second planning for the same
  study+subject in a different course with different ponderations, and confirms the correct one
  (matching the record's own course / the live session's current course, respectively) is the one
  actually used.

## Phase 4 — force "Nota del centre" in the grade review wizard, Esfera-style — IMPLEMENTED AND
TESTED 2026-09-23 (redesigned the same day — the paragraph below replaces an earlier, wrong
design that touched `ems.grade_subject_line`/the live grade matrix widget instead; that screen
is untouched by this phase, confirmed with the developer via a screenshot)

**What it's actually for:** `ems.grade_review_wizard` (post-closure correction of a
`ems.student.year_record.subject`, NOT the live in-course grading screen) shows a "Result of the
review" group with `preview_internal_grade` ("Nota del centre" in Catalan — confirmed via
`i18n/ca_ES.po`'s `field_ems_grade_review_wizard__preview_internal_grade` block) and
`preview_final_grade` ("Nota final"), both purely computed from the RA outcome grid above. Esfera
(the official external system) can carry a slightly different number for the same subject due to
its own rounding — the developer needs to type Esfera's number directly instead of
reverse-engineering fake RA scores that happen to average out to it. **Only "Nota del centre" gets
forced — "Nota final" and "Estat" are explicitly NOT touched by this phase**, confirmed 2026-09-23.

**Safeguard (explicit developer requirement, screenshot-confirmed):** forcing the grade must
NEVER be able to flip whether the subject is actually passed. If any RA is below 5 (state would
compute `'failed'`), the forced value must stay below 5; if every RA is at 5+ (state `'passed'`),
the forced value must stay at 5+. Only the exact number within that side can be corrected, never
the side itself.

**Model changes (`models/grades/grade_review_wizard.py`):**
- New field `override_internal_grade = fields.Boolean(string="Force internal grade")`.
- `preview_internal_grade` gains `readonly=False` on its declaration, now computed by its OWN
  method (`_compute_preview_internal_grade`) — see the correction below for why it was split out
  of `_compute_preview`.
- **Correction, confirmed empirically 2026-09-23**: a first version kept `preview_internal_grade`
  computed by the SAME `_compute_preview` method that also derives `preview_final_grade`. This
  does not work — writing a value into a `readonly=False` compute field does not retrigger the
  very method that outputs it (there is no self-dependency), so `preview_final_grade` silently
  kept using the stale, un-overridden value (`0` for a fresh wizard) instead of reacting to the
  forced grade. Fixed by splitting into two methods, mirroring the exact pattern
  `ems.grade_subject_line` already uses for `internal_score`/`computed_score`:
  `_compute_preview_internal_grade` (skips itself when `override_internal_grade` is set, same
  `@api.depends` list as before) and `_compute_preview` (now also depends on
  `preview_internal_grade` itself, so it reliably reruns whenever that value changes, whether by
  computation or by a direct override write) — `preview_state` still comes from `_subject_values()
  ['state']` inside `_compute_preview`, untouched by the override, and
  `preview_final_grade`/`preview_has_final` are (re)derived from whatever `preview_internal_grade`
  now is via `self.env['ems.grade_subject_line']._final_from_parts(...)`.
- New `@api.constrains('override_internal_grade', 'preview_internal_grade')`
  (`_check_override_internal_grade`): when the override is active, raises a `ValidationError` if
  the value is outside `[0, 10]`, or if `(preview_internal_grade >= 5) != (preview_state ==
  'passed')` — the safeguard, phrased as two distinct messages (below 5 required vs. 5-or-above
  required) so the reviewer understands which RA-driven side they're not allowed to cross.

**Application changes, same file — the part that makes the override actually persist:**
Today, `_apply_correct()`/`_apply_add()` write the RA line changes and then unconditionally call
`_recompute_from_outcomes()`, which re-derives `internal_grade`/`state`/`final_grade`/`has_final`
straight from the outcomes and resets `is_overridden` to `False` — the wizard's own preview is
**never actually what gets saved** today, so adding the field alone would not be enough.
- New shared helper `_apply_internal_grade_override(self, subject_record)`: no-op (`return
  None`) when `override_internal_grade` is off. Otherwise, captures
  `subject_record.internal_grade` (the natural, just-recomputed value) for the audit message,
  then `subject_record.write({'internal_grade': self.preview_internal_grade, 'is_overridden':
  True, 'final_grade': <recomputed via _final_from_parts>, 'has_final': <same>})` — reusing
  `ems.student.year_record.subject.is_overridden` (already exists, currently only ever set from
  the live `ems.grade_subject_line.is_overridden` at freeze time and cleared by
  `_recompute_from_outcomes()`; same "this grade isn't purely outcome-derived" meaning, no new
  field needed). `state` is deliberately never touched here — the constraint above already
  guarantees it's consistent with the forced value by the time this runs. Returns an audit
  message (`_("Internal grade forced manually: %(forced)s (RA average would give
  %(natural)s)", ...)`) or `None`.
- Call it from `_apply_correct()` right after `self._history(self.subject_record_id)
  ._recompute_from_outcomes()`, and from `_apply_add()` right after `subject_record
  ._recompute_from_outcomes()`, in both cases BEFORE building the existing "subject: state →
  state (grade X)" chatter message (so it reports the final, possibly-forced grade), appending
  the override's own audit line to `changes`/the returned list when not `None`.
- `_apply_correct()`'s existing guard `if not changes: raise UserError(...)` (today: "the review
  does not change any learning outcome grade") must become `if not changes and not
  self.override_internal_grade: raise UserError(...)` — forcing the internal grade with zero RA
  line edits is a legitimate, standalone correction (the exact scenario the developer described:
  every RA score is already right, only the weighted-average rounding disagrees with Esfera).

**View (`views/planning_grading/grading/year_record/grade_review_wizard.xml`, "Result of the
review" group):** the `override_internal_grade` checkbox sits next to `preview_internal_grade`,
whose `readonly` is now conditional on it (`readonly="not override_internal_grade"`) so it's
visually locked until the reviewer opts in. **Not screenshot-verified this session** — a
deliberate, reasoned call, not an oversight: this is plain, standard `readonly="..."` view-attr
syntax (the same pattern used dozens of times elsewhere in this codebase, no custom OWL/JS
involved), and the Form-based tests above already exercise this exact view's arch end to end
(`Form(..., view='ems.view_grade_review_wizard_form')` — a malformed view would have failed
those tests outright, not just looked wrong). Worth a quick visual glance next time this screen
is open, but not treated as a blocking gap for this phase.

**Shared for both `correct` and `add` operations** — the mechanism is generic and both already
go through the same `_compute_preview()`/`_recompute_from_outcomes()` path, so there's no extra
cost to supporting both; the developer's own example was `correct` specifically. If it turns out
`add` shouldn't offer this, restricting the checkbox to `invisible="operation != 'correct'"` in
the view is a one-line follow-up, not a redesign.

**Tests (`tests/test_grade_review.py`, 4 new cases, 31 tests total in the class, all green):**
- `test_override_forces_internal_grade_and_recomputes_final`: forcing a value on the same side
  as the computed state applies cleanly, is reflected in `preview_final_grade` automatically, and
  ends up written on `ems.student.year_record.subject` (`internal_grade`, `is_overridden=True`,
  `final_grade` recomputed) after `action_apply()`. `preview_state`/the record's own `state` stay
  whatever the RAs say, untouched. **Built via `Form` up to `.save()` (for the line_ids/onchange
  plumbing), then the override itself is set via a direct `wizard.write()`** — deliberate, not
  incidental: `preview_internal_grade` has no `@api.onchange` of its own (a plain `readonly=False`
  compute, same as `ems.grade_subject_line.internal_score`), so it isn't built to be driven
  through `Form`'s onchange-simulation the way a field with its own onchange is; a first attempt
  to set it via `form.preview_internal_grade = X` silently didn't stick by the time `.save()` ran.
- `test_override_cannot_force_a_pass_when_a_ra_still_fails` /
  `test_override_cannot_force_a_fail_when_every_ra_passes`: forcing a value on the WRONG side of
  5 relative to the computed state raises `ValidationError`, both directions.
- `test_override_applies_with_no_outcome_line_changed`: forcing with zero RA line edits (no
  `changes` otherwise) still applies, instead of hitting the old "no changes" `UserError`.
- No tour needed: this is a backend wizard field with no new client-side widget, standard Odoo
  list/form rendering handles the readonly toggle already (see `feedback_ui_view_changes_need_
  tour_coverage` — this genuinely is the narrow case that doesn't apply, since nothing here is a
  custom OWL component; a plain `TransactionCase` on `action_apply()` already proves the write
  path end to end).

## Implementation order

Phase 2 (this plan) depends on [[plans/current_course_auto_seed]] landing first (or in the very
same PR/version bump - they share one migration version, see that plan's "Left for whoever
implements this"). Phase 3 depends on phase 2. Phase 4 is independent and can land before or
after either.

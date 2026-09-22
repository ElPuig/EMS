# Issue #503 — link `ems.planning` to an academic course

**Status: current, not started. Design closed 2026-09-22/23 across several sessions — ready to
implement.** Nothing described here has been coded yet, except Phase 1 (see "Overall issue
roadmap" below), which already landed. If the planning/course/grading code changes significantly
before this is picked up, re-verify the details below before acting on them.

**Hard dependency: [[plans/current_course_auto_seed]] (v2).** That plan's `ems.course_bootstrap`
placeholder mechanism is what makes `ems.planning.course_id` safe to make required at all — read
it first, this plan assumes it's already understood.

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

### Model changes (`models/planning/planning.py`)

- New field: `course_id = fields.Many2one("ems.course", required=True, default=lambda self: self.env.company.current_course_id)`.
  The default is safe for any UI-driven creation (by then `current_course_id` is always
  meaningfully set, either by an admin or by
  [[plans/current_course_auto_seed]]'s fresh-install seed) — it is NOT relied upon for
  CSV-created rows, see below.
- `_sql_constraints`: `unique(study_id, subject_id)` → `unique(study_id, subject_id, course_id)`.
- `_compute_name`: include the course, so two years' plannings for the same study+subject are
  distinguishable in list views (today's format is `"%s  %s" % (study.acronym, subject.name)`;
  append the course's own `name`, e.g. `"CFGS DAM2  Programació (2025-2026)"`). Update
  `TestPlanningLogic.test_compute_name` (`tests/test_planning.py`) accordingly - it currently
  asserts the course-less format.

### The centre's own seed data (`data/custom/ccff/ems.planning-*.csv`, 9 files, NOT the
`_outcome` companion files)

Add a `course_id/id` column, pointing at **`ems.course_bootstrap`**
(see [[plans/current_course_auto_seed]]) — NOT at a real, hardcoded course. Two reasons, both
already argued through with the developer:

1. `data/custom/ems.course.csv` (the file that used to seed this centre's real, fixed
   2025-2029 courses) is being **deleted** as part of this same body of work (see "Deleting
   `data/custom/ems.course.csv`" below) — there would be no real course xmlid left to point at
   on a fresh install anyway.
2. Even if it still existed, a fixed historical anchor (e.g. always `2025-2026`) would be wrong
   on principle: these ponderations have always been a single, timeless, ever-current
   configuration (there was no course concept before this issue) - anchoring them to whatever
   course [[plans/current_course_auto_seed]] resolves as "current" for the install is the more
   honest choice, and it's exactly what that plan's placeholder mechanism already provides for
   free (any row pointing at `ems.course_bootstrap` gets carried along automatically when the
   post_init_hook step corrects or reassigns it).

No manifest reordering needed: `data/main/ems.course.csv` (new, from the dependency plan) already
sits well before `data/custom/ccff/ems.planning-*.csv` in `__manifest__.py`'s existing data list.

### Rollover at course transition (`models/settings/course_transition_wizard.py`)

New `_apply_planning_rollover()`, called from `action_apply()`, scoped to `self.study_ids` (same
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

`copy()` alone is enough to duplicate `planning_outcome_ids` too — neither that field nor
`internal_ponderation`/`external_ponderation` set `copy=False`, so Odoo's default `copy()`
already duplicates the outcome lines. `name` (computed, `store=True`, no explicit `copy=True`)
is NOT copied and gets recomputed from `study_id`/`subject_id`/`course_id`, which are copied -
no manual handling needed there.

Idempotent by construction: relaunching a transition (or the same target course across two
separate runs) skips any study+subject that already has a target-course planning.

### Migration for THIS already-existing install (and any other pre-#503 install)

A `post-migrate.py` in the same version bump as phase 2's model change (new column →
post-migrate, not pre-migrate). **Independent of, and simpler than,
[[plans/current_course_auto_seed]]'s own migration** — this one only needs to replicate history,
not seed anything from scratch:

```python
def _replicate_plannings_across_history(env):
    current = env.company.current_course_id
    if not current:
        return
    courses = env['ems.course'].search([('start', '<=', current.start)], order='start asc')
    if not courses:
        return
    for planning in env['ems.planning'].search([]):
        planning.course_id = courses[0].id
        for course in courses[1:]:
            planning.copy({'course_id': course.id})
```

On this dev DB (mirroring real production) this replicates every existing planning across
2024-2025, 2025-2026 and 2026-2027 (the current course) — not the not-yet-run 2027-2028/2028-2029,
which the rollover above will create for real once the centre actually transitions into them.
Does not reference any xmlid — purely operates on whatever `ems.course` rows already exist,
regardless of whether `data/custom/ems.course.csv` still exists by then (it won't, see below).

### Deleting `data/custom/ems.course.csv`

Confirmed safe (developer request, 2026-09-22): the 4 courses it seeds
(`__import__.ems_course_25_26` through `_28_29`) are `__import__`-owned. Per this project's own
documented `_process_end` mechanism (CLAUDE.md, "Data folder conventions"), a `module='__import__'`
record is never even a candidate for Odoo's data-file cleanup, regardless of whether the file that
originally declared it still exists. Deleting the file (and its manifest line) leaves the 4
already-created courses in this DB completely untouched, forever. Nothing else in the codebase
references these 4 specific xmlids outside already-applied historical migration scripts
(`migrations/18.0.0.8.0`, `18.0.0.22.0` — verified via grep, 2026-09-22). The file's removal
requires no migration step of its own.

### Tests

- `tests/test_planning.py` (`TestPlanningLogic`): the unique constraint now permits two
  plannings for the same study+subject across different courses, and still blocks a duplicate
  within the same course. Update `test_compute_name` for the course-inclusive name format.
- `tests/test_course_transition.py`: new case asserting the target course gets one planning
  (with matching ponderations/outcome lines) per source-course planning after `action_apply()`,
  and that relaunching a transition never duplicates one.
- No new tour needed for phase 2 alone — no new view surface (see phase 3/4 for where a tour
  does apply).

## Phase 3 — grade correction uses the correct year's planning (already designed, unaffected by
the phase-2 refinements above — depends only on `course_id` existing)

- `models/grades/grade_review_wizard.py::_fill_lines()` (`operation == 'add'` branch, currently
  around line 143-148): add `('course_id', '=', self.record_id.course_id.id)` to the planning
  search domain. `self.record_id` (`ems.student.year_record`) already has its own `course_id`.
- `models/grades/grade_session.py::_compute_planning_id()` (around line 37-45): add
  `('course_id', '=', session.env.company.current_course_id.id)` — live grade sessions only ever
  target the current course.
- **Regression tests, the actual point of this phase**: create two plannings for the same
  study+subject in two different courses with different ponderations; verify a grade-review
  correction against an old-course `year_record` picks up the OLD course's weights, and that
  `grade_session._compute_planning_id` picks the CURRENT course's one when both exist for the
  same study+subject.

## Phase 4 — force "Nota del centre" in the grade review wizard, Esfera-style (REDESIGNED
2026-09-23 — the paragraph below replaces an earlier, wrong design that touched
`ems.grade_subject_line`/the live grade matrix widget instead; that screen is untouched by this
phase, confirmed with the developer via a screenshot)

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
- `preview_internal_grade` gains `readonly=False` on its declaration (stays
  `compute='_compute_preview'`).
- `_compute_preview()`: add `'override_internal_grade'` to its `@api.depends`. When
  `override_internal_grade` is set, skip overwriting `preview_internal_grade` (the reviewer's
  typed value survives). `preview_state` keeps coming from `values['state']` exactly as today,
  UNCHANGED by the override — this is what the safeguard below cross-checks against.
  `preview_final_grade`/`preview_has_final` must stop trusting `values['final_grade']` (computed
  from the UN-overridden internal grade) and instead always be (re)derived from whatever
  `preview_internal_grade` ends up being — forced or computed — via
  `self.env['ems.grade_subject_line']._final_from_parts(wizard.preview_internal_grade, True,
  external_grade, external_is_scored, internal_weight, external_weight)` (the same helper
  `_subject_values()` already uses internally, so the formula never forks in two places).
- New `@api.constrains('override_internal_grade', 'preview_internal_grade')`
  (`_check_override_internal_grade`): when the override is active, raise a `ValidationError` if
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
review" group):** add the `override_internal_grade` checkbox next to `preview_internal_grade`,
and make the latter's `readonly` conditional on it (`readonly="not override_internal_grade"`) so
it's visually locked until the reviewer opts in — exact placement/labeling to be self-verified
with a screenshot before considering this phase done (per the project's own "self-verify UI"
standing habit), not nailed down further in this design doc.

**Shared for both `correct` and `add` operations** — the mechanism is generic and both already
go through the same `_compute_preview()`/`_recompute_from_outcomes()` path, so there's no extra
cost to supporting both; the developer's own example was `correct` specifically. If it turns out
`add` shouldn't offer this, restricting the checkbox to `invisible="operation != 'correct'"` in
the view is a one-line follow-up, not a redesign.

**Tests (`tests/test_grade_review.py`):**
- Forcing a value on the same side as the computed state applies cleanly, is reflected in
  `preview_final_grade` automatically, and ends up written on `ems.student.year_record.subject`
  (`internal_grade`, `is_overridden=True`, `final_grade` recomputed) after `action_apply()`.
  `preview_state`/the record's own `state` stay whatever the RAs say, untouched.
  - Forcing a value on the WRONG side of 5 relative to the computed state raises
  `ValidationError`, for both directions (trying to force ≥5 when a RA fails; trying to force <5
  when every RA passes).
- Forcing with zero RA line edits (no `changes` otherwise) still applies, instead of hitting the
  old "no changes" `UserError`.
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

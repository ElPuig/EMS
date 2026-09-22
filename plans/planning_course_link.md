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

## Phase 4 — manual final score override, Esfera-style (already designed, fully independent of
`ems.course`/phases 2-3)

- `ems.grade_subject_line`: new `is_final_overridden` boolean; `final_score` gets its own
  `_compute_final_score` (`compute=..., store=True, readonly=False`), mirroring the existing
  `internal_score`/`is_overridden` pattern exactly — skip the compute when overridden.
  `_compute_has_final` must treat an override the same way it already treats
  `internal_is_scored`/`internal_is_complete` when `is_overridden` is set (an incomplete
  evaluation with a manually-forced final score must still count as "has final").
- Widget (`static/src/js/backend/grade_matrix_field.js` + its `.xml`): replicate the existing
  `internal_score` override UI (checkbox + editable cell) for the final-score column - today it's
  a read-only computed column with no edit affordance at all, despite the view's own alert text
  (`views/planning_grading/grading/form.xml:13-16`) already promising "you can still... set the
  final grade manually," which isn't actually possible yet - this phase fixes a real, already
  user-visible broken promise, not just an enhancement.
- Tests + tour extension (`grade_matrix_tour.js`/`test_grade_matrix_tour.py`): set the override,
  confirm it survives an outcome score changing; confirm unsetting it recomputes from
  `computed_score`.

## Implementation order

Phase 2 (this plan) depends on [[plans/current_course_auto_seed]] landing first (or in the very
same PR/version bump - they share one migration version, see that plan's "Left for whoever
implements this"). Phase 3 depends on phase 2. Phase 4 is independent and can land before or
after either.

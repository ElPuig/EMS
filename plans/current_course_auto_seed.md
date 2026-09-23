# Auto-seed the "Current course" (`current_course_id`) on install

**Status: IMPLEMENTED 2026-09-23 (v3 below).** `./upgrade.sh` verified clean on this dev DB
across two consecutive runs after implementation, confirming the mechanism is stable and does
not regress on a subsequent upgrade (the exact failure mode that sank v2 — see "Revision
history"). Kept here for context/history rather than deleted immediately, since the surrounding
issue #503 work ([[plans/planning_course_link]]) is still being verified end to end.

## Why

`res.company.current_course_id` ("Curso actual") is never auto-seeded: neither `post_init_hook`
nor any migration touches it. The code itself already documents this as a known gap
(`res.company.get_current_course_or_raise()`, `models/settings/company.py:109-121`):

> "nothing guarantees an admin has already set it on a freshly installed instance, or in a
> test DB that never configured one."

This surfaced as two real bugs found 2026-09-09 in `tests/test_absence.py`/`test_absence_tour.py`
while reproducing CI PR #426's failure on a genuinely clean install: `date_range()` on an empty
`current_course_id` returns `False`, and code that assumed a course was already configured broke
with `TypeError: 'bool' object is not subscriptable`. Both were worked around locally (the test
classes now create a fallback course themselves, mirroring `test_guard_duty_board.py`'s existing
pattern — see `tests/test_absence.py:355-362`, which creates a `1999-2000` filler course when
`current_course_id` is empty). **That workaround stays — see "Interaction with tests" below,
this fix does not remove it.**

A sibling mechanism already does exactly this, for a different field:
`ems.course._ems_seed_enrollment_default()` (`models/settings/course.py:46-86`) auto-seeds
`is_enrollment_default`/`res.company.enrollment_course_id` from `post_init_hook` (fresh installs)
and from `migrations/18.0.0.22.0/post-migrate.py` (existing installs). The final design below
builds the equivalent for `is_current`/`current_course_id`.

## Design as implemented (v3, 2026-09-23)

**`_ems_seed_current_course(env)` (`__init__.py`), called from `post_init_hook` right before the
existing `_ems_seed_enrollment_default()` call** (that method's own "course after the operational
one" logic already depends on `is_current` being meaningful — seeding the current course first
lets it hit its intended branch instead of always falling back to "the earliest course"):

```python
def _ems_seed_current_course(env):
    year = datetime.now().year
    course = env['ems.course'].search([('start', '=', year)], limit=1) \
        or env['ems.course'].create({'start': year, 'end': year + 1})
    env['res.company'].search([]).write({'current_course_id': course.id})
```

No September/August academic-year cutover logic — explicitly decided against by the developer
2026-09-22: *"podría ser 2029-2030 o 2028-2029 [dependiendo del mes], pero... no vale la pena
meterse en eso ahora."* A plain calendar year (`datetime.now().year`) is enough.

Reuses an existing course for that year if a centre's own data (e.g. a `data/custom/`-style seed
file) already created one, rather than creating a duplicate — `ems.course`'s own
`unique_course_name` constraint would block that anyway, so this is just avoiding the error
rather than working around a real ambiguity.

**Migration for an already-existing install** (`migrations/18.0.0.28.0/post-migrate.py`,
`_backfill_current_course_id`): backfills `current_course_id` only on a company that doesn't have
one yet, using whichever course already carries `is_current=True` if any does. A no-op for this
dev DB / the real production it mirrors, both already configured — exists only for some other
already-existing install that somehow never configured it.

## Interaction with `ems.planning.course_id` (issue #503) — why v3 needs nothing at data-load time

[[plans/planning_course_link]]'s `ems.planning.course_id` is what originally made this problem
urgent (see "Revision history" for the failed detour that caused) — but the FINAL design there
does **not** require a real `ems.course` to exist while data files load at all: `course_id` is
NOT `required=True` at the field/DB level, only enforced at the application level via a
`@api.constrains` that skips itself during `install_mode` (the exact same escape hatch
`check_ponderation` on the same model already uses). A data-file-created planning row is simply
left with `course_id` empty until `post_init_hook` backfills it, right after this function runs.
This is what makes the simple v3 design above sufficient — no placeholder record, no data file of
its own, needed at all.

## Interaction with tests

`./test.sh` on this box always **upgrades** the existing `ems` database, never performs a clean
install (see `feedback_local_db_never_exercises_post_init_hook` in memory) — `post_init_hook`
never runs during any local test run. This means `test_absence.py`'s own `1999-2000` filler-course
fallback (and any other test with the same pattern, e.g. `test_guard_duty_board.py`,
`test_course_transition.py`, `test_year_record.py`) **remains necessary regardless of this fix**
— it is not something this fix makes obsolete. Only a genuinely clean-install run (CI's own
install step, or a fresh local `-i ems`) would ever exercise `_ems_seed_current_course()` at all
— not yet verified on an actual clean install in this session, only by direct code review; worth
a real `-i ems` run before considering issue #503 fully closed.

## Left to do

- Tests, mirroring `test_course.py`'s existing "seeding the enrollment default" section: creates
  a course for the current year when none exists; reuses an existing one for that year instead of
  duplicating; the migration's backfill leaves an already-configured company untouched.
- A real clean-install (`-i ems` on a blank database) run, to verify `_ems_seed_current_course`
  end to end rather than only by code review — not yet done this session.

## Revision history

- **2026-09-09/17 (v1, superseded):** proposed scanning existing courses via `date_range()` for
  one whose real Sept-Aug window contains today, creating a fresh course with real academic-year
  boundaries if none matched, entirely from within `post_init_hook`/migration — no placeholder
  record. Correct for the problem as understood at the time (`current_course_id` alone), but once
  issue #503 (below) needed `ems.planning.course_id`, a post_init_hook-only fix looked
  insufficient because a data-file-created planning row would need a valid FK before
  post_init_hook ever runs.
- **2026-09-22 (v2, superseded — implemented, then reverted the same night after failing on
  re-test):** introduced a placeholder `ems.course_bootstrap` (1900-1901) seeded via a new
  `data/main/ems.course.csv`, corrected in place by `post_init_hook`, with `ems.planning.course_id`
  (then still `required=True`) pointing centre CSV rows at it. **Confirmed broken empirically
  2026-09-23**, on the SECOND consecutive `./upgrade.sh` run (the exact scenario that matters,
  since a real install upgrades many times over its life, not once): `data/main/ems.course.csv`
  reloads on every upgrade like any other `noupdate=False` data file, so once the placeholder was
  correctly deleted after the first run, the second run's data reload silently RECREATED it (a
  new row, new id) — and since the centre's own `data/custom/ccff/ems.planning-*.csv` rows also
  had `course_id/id` pointing at that same xmlid as a synced column, that SAME reload reverted
  132 already-correctly-migrated planning rows' `course_id` back to the newly-recreated
  placeholder, undoing the whole migration. This is the exact "CSV resync stomps a value that
  must not be perpetually resynced" trap CLAUDE.md's own data-loading conventions already warn
  about for a different case (`ems.group`'s living-data fields) — not spotted while designing v2
  because the interaction only shows up on a *second* upgrade, and the first attempt looked
  completely successful. Replaced by v3 the same night once this was found, by making
  `ems.planning.course_id` NOT require a value at data-load time at all (see
  [[plans/planning_course_link]]), which removed the entire reason a placeholder was needed in
  the first place.

# Auto-seed the "Current course" (`current_course_id`) on install

**Status: current, not started. Redesigned 2026-09-22 (see "Revision history" below) — this
supersedes the original design in every detail except the underlying problem statement.** No
code has been written for either version yet. If the course/company code changes significantly
before this is picked up, re-verify the details below before acting on them.

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
this plan does not remove it.**

A sibling mechanism already does exactly this, for a different field:
`ems.course._ems_seed_enrollment_default()` (`models/settings/course.py:46-86`) auto-seeds
`is_enrollment_default`/`res.company.enrollment_course_id` from `post_init_hook` (fresh installs)
and from `migrations/18.0.0.22.0/post-migrate.py` (existing installs). This plan builds the
equivalent for `is_current`/`current_course_id`, in a similar shape but NOT the same mechanism
internally (see below) — a second, independent need surfaced while designing issue #503 that the
original design (post_init_hook-only) cannot satisfy.

## Why this became a hard *blocker* for other work, not just a nice-to-have (2026-09-22)

Issue #503 ("Grade correction: get the correct course planification") needs
`ems.planning.course_id` to become a **required** field (see
[[plans/planning_course_link]] for that plan). This exposed a timing problem the original design
never had to deal with:

- Data files (CSV/XML, including the centre's own `data/custom/ccff/ems.planning-*.csv`) load
  **during** installation.
- `post_init_hook` runs **once, after every data file has already loaded**.
- A required `ems.course` FK on a record created BY a data file (a planning row) needs a valid
  value **at data-load time** — long before any post_init_hook logic could create or resolve one.

The original design below (v1) only ever acted from inside `post_init_hook`/a migration script —
it could never help a data-file-created record satisfy a required FK during the load itself. A
placeholder record seeded by a *data file itself* is the only way to give such a record something
valid to point at before the real value is knowable.

## Design (v2, 2026-09-22)

**A placeholder `ems.course`, seeded by a plain data file, corrected in place afterwards —
not date-range detection, not creating a fresh record.**

1. **`data/main/ems.course.csv`** (new, generic — NOT under `data/custom/`, this belongs to EMS
   itself, not to any one centre): a single row, `id=course_bootstrap` → `ems.course_bootstrap`,
   `start=1900, end=1901`. Deliberately an absurd, obviously-wrong year: if the correction step
   below ever fails to run, it's immediately obvious in the UI rather than silently wrong.
   - Any OTHER data-file record that needs a real `ems.course` FK to be created (today: only
     `ems.planning.course_id`, seeded by the centre's own `data/custom/ccff/ems.planning-*.csv` —
     see [[plans/planning_course_link]]) points at this same xmlid. This is what makes step 2's
     "correct it in place" approach valuable: fixing the ONE placeholder record automatically
     fixes everything that already pointed at it, with no separate reassignment needed in the
     common case.
2. **New `post_init_hook` step**, e.g. `_ems_seed_current_course(env)` (`__init__.py`), run
   **before** the existing call to `_ems_seed_enrollment_default()` (that method's own "course
   after the operational one" logic already depends on `is_current` being meaningful — today it
   always finds it empty and falls back to "the earliest course"; seeding the current course
   first lets it hit its intended branch):
   ```python
   def _ems_seed_current_course(env):
       bootstrap = env.ref('ems.course_bootstrap', raise_if_not_found=False)
       if not bootstrap:
           return
       year = datetime.now().year
       existing = env['ems.course'].search([('start', '=', year), ('id', '!=', bootstrap.id)], limit=1)
       if existing:
           # A centre's own data file already seeds a real course for this exact year (e.g. one
           # recreating the pattern the old data/custom/ems.course.csv used before it was
           # removed - see [[plans/planning_course_link]]). Reuse it; the placeholder becomes
           # redundant. Reassign anything that already points at it BEFORE unlinking, or the
           # required FK blocks the unlink. Today, only ems.planning.course_id does this - add
           # its own line here if/when another course-dependent seed model appears.
           env['ems.planning'].search([('course_id', '=', bootstrap.id)]).write({'course_id': existing.id})
           bootstrap.unlink()
           course = existing
       else:
           # Common case: nothing else has claimed this year yet - correct the placeholder
           # in place (same id), so anything that already referenced it is now correct too.
           bootstrap.write({'start': year, 'end': year + 1})
           course = bootstrap
       env['res.company'].search([]).write({'current_course_id': course.id})
   ```
3. **No September/August academic-year cutover logic** (the original v1 design's `date_range()`
   scan was built to handle this). Explicitly decided against by the developer 2026-09-22:
   "podría ser 2029-2030 o 2028-2029 [dependiendo del mes], pero... no vale la pena meterse en
   eso ahora." A plain calendar year (`datetime.now().year`) is enough; refining this to a real
   Sept-Aug cutover is left as unstarted future work if it's ever actually needed, not part of
   this plan.
4. **Migration for an already-existing install**: a `post-migrate.py` in the same version bump
   (new column/logic → post-migrate, not pre-migrate) that runs the equivalent
   "backfill `current_course_id` only if still empty" safety net — mirroring
   `_ems_seed_enrollment_default`'s own "don't touch an already-decided company" guard. For an
   install that already has `current_course_id` configured (this dev DB / the real production it
   mirrors both already do), this is a no-op. It exists only for some OTHER already-existing
   install out there that somehow never configured it. **Does not need to know about, or touch,
   `ems.course_bootstrap` at all** — that xmlid never gets created on the upgrade path (data/main
   files DO reload on every upgrade too, so a bare `ems.course_bootstrap` row WOULD appear unless
   explicitly deleted — see the note below).
5. **A newly-introduced generic xmlid reloading into an already-existing DB on upgrade**: since
   `data/main/ems.course.csv` is a normal, `noupdate=False` data file, it reloads on every
   upgrade, not just on a fresh install - an already-existing database (this one included) WOULD
   get a stray `1900-1901` course created the first time it upgrades into the version that
   introduces this file, and nothing would ever fix it (post_init_hook never runs on upgrade).
   The same version's migration step must therefore also **delete `ems.course_bootstrap`
   unconditionally** on the upgrade path, right after data reload (post-migrate timing):
   ```python
   bootstrap = env.ref('ems.course_bootstrap', raise_if_not_found=False)
   if bootstrap:
       bootstrap.unlink()
   ```
   An upgrading install has no use for the placeholder at all - it already has a real, configured
   `current_course_id` (or gets one from step 4's backfill above), so there's nothing to reassign
   onto it first.

## Interaction with tests (unchanged from v1's finding, restated for clarity)

`./test.sh` on this box always **upgrades** the existing `ems` database, never performs a clean
install (see `feedback_local_db_never_exercises_post_init_hook` in memory) — `post_init_hook`
never runs during any local test run. This means `test_absence.py`'s own `1999-2000` filler-course
fallback (and any other test with the same pattern, e.g. `test_guard_duty_board.py`,
`test_course_transition.py`, `test_year_record.py`) **remains necessary regardless of this fix**
— it is not something this plan makes obsolete. Only a genuinely clean-install run (CI's own
install step, or a fresh local `-i ems`) would ever exercise `_ems_seed_current_course()` at all.

## Left for whoever implements this

- Whether to log a `_logger.warning` when the collision branch fires (a centre's own data already
  claimed the current year) — useful signal, not required.
- The exact next manifest version number for the migration folder: **do not bump
  `__manifest__.py` without the developer's explicit go-ahead** (existing CLAUDE.md rule) —
  propose it and wait for confirmation before creating `migrations/<version>/`. This plan and
  [[plans/planning_course_link]] both need a migration in the SAME version bump (they're one
  piece of work, see that plan for why) - do not create two separate version folders for them.
- Tests, mirroring `test_course.py`'s existing "seeding the enrollment default" section: the
  common case (placeholder corrected in place, company backfilled); the collision case (a
  pre-existing real course for the install year reused, placeholder discarded, referencing
  `ems.planning` rows reassigned); re-running is safe (idempotent); the upgrade-path migration
  deletes a freshly-reloaded placeholder and leaves an already-configured company untouched.

## Revision history

- **2026-09-09/17 (v1, superseded):** proposed scanning existing courses via `date_range()` for
  one whose real Sept-Aug window contains today, creating a fresh course with real academic-year
  boundaries if none matched, entirely from within `post_init_hook`/migration — no placeholder
  record. Correct for the problem as understood at the time (`current_course_id` alone), but
  cannot satisfy a data-file-created record's required `ems.course` FK, since post_init_hook
  necessarily runs after all data has already loaded. Replaced 2026-09-22 once issue #503
  surfaced that exact need.

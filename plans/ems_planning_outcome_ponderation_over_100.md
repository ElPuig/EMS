# 5 plannings whose outcome ponderations sum to 106%, not 100%

**Status: current, found 2026-09-23, NOT fixed.** Discovered as a side effect of issue #503's
`ems.planning.course_id` migration (`migrations/18.0.0.28.0/post-migrate.py`), not something
this box was already tracking.

## What was found

```sql
SELECT p.id, p.name, SUM(po.ponderation) as total
FROM ems_planning p
LEFT JOIN ems_planning_outcome po ON po.planning_id = p.id
GROUP BY p.id, p.name
HAVING ROUND(SUM(po.ponderation)::numeric, 2) != 100 OR SUM(po.ponderation) IS NULL;
```

Returns 5 rows, all the SAME subject ("MP 1665: Digitalització aplicada als sectors productius"),
one per study (ASIX, DAM, DAW, AIF, AD) — every one sums to **106%**, not 100%.

## Why this was never caught before

`ems.planning.check_ponderation()` (`models/planning/planning.py`) already enforces "outcome
ponderations must sum 100" — but it explicitly skips itself when `self.env.context.get(
"install_mode")` is set, which is exactly the context every `data/custom/ccff/*.csv` row loads
under. These 5 rows were seeded that way and have never been written to since (the constraint
only fires on `create()`/`write()`, never on a plain read) — so the inconsistency has been
sitting silently in this dataset the whole time, undetected until issue #503's migration tried
to `copy()` these rows (a NORMAL, non-install-mode `create()`) and the constraint fired for real
for the first time.

## How the migration handles it (not a fix, a deliberate non-fix)

`_replicate_plannings_across_history()` wraps its `copy()` calls in
`with_context(install_mode=True)`, the same escape hatch the original CSV load already uses —
this replicates the already-live (already wrong) data across the historical courses unchanged,
rather than silently "fixing" a centre-authored curriculum percentage on its way through an
unrelated migration. Which specific outcome's ponderation should actually change is a curriculum
content decision for the centre to make, not something a migration script should guess.

## What's actually needed

- Confirm with the developer whether these 5 rows are a genuine data-entry mistake (most likely,
  given all 5 point at the exact same subject/module) or intentional for some reason not visible
  from the data alone.
- If a mistake: correct `data/custom/ccff/ems.planning_outcome-*.csv` (whichever files declare
  `ems.subject_1665`'s outcome ponderations for ASIX/DAM/DAW/AIF/AD) so they sum to 100 again,
  and the same fix will apply to this dev DB (and real production) on its next `./upgrade.sh`,
  since these are `noupdate=False` `__import__`-owned rows.
- Optional: a one-time `_logger.warning` audit sweep (or a standalone script) checking every
  `ems.planning` for this exact condition, in case there are OTHER silently-invalid rows besides
  this subject - this discovery only surfaced the ones affected by issue #503's migration; there
  could be others `check_ponderation` has never been exercised against yet.

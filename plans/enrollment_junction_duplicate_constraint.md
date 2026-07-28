# PLAN — `ems.enrollment` has no uniqueness constraint on (student, group, subject)

> **Status: flagged during the `ems.enrollment` (contacts junction) DTON pass (2026-07-28),
> not implemented.** This is not a design for new work — it's an open question for whoever
> owns the attendance/grading data model to answer before any fix is written. Nothing below
> has been built. Verify file/line references and the duplicate count against current code
> and data before acting, since both may have moved on since this was written.
>
> Lives under `plans/` per `CLAUDE.md`'s "Design plans" convention — delete this file once
> the question is resolved (fixed, or explicitly decided as intentional and documented in
> `docs/en/developers/contacts/enrollment.md`).

## Problem

`ems.enrollment` (`models/contacts/enrollment.py`, `EmsEnrollment`) is the ternary junction
row **student × group × subject** — the single source of truth for whether a student is
"in" a subject, read by `ems.attendance_template` and `ems.grade_session` to generate
attendance/grade lines. The model has no `_sql_constraints` (or any other guard) preventing
the same `(student_id, group_id, subject_id)` triple from being inserted more than once.

## What this means concretely

A direct query of the production database (2026-07-28) found existing duplicates:

```sql
SELECT count(*) AS duplicate_groups, sum(cnt) AS duplicate_rows FROM (
  SELECT student_id, group_id, subject_id, count(*) AS cnt
  FROM ems_enrollment
  GROUP BY student_id, group_id, subject_id
  HAVING count(*) > 1
) t;

 duplicate_groups | duplicate_rows
-------------------+----------------
                21 |             42
```

21 distinct (student, group, subject) combinations have exactly 2 rows each (42 rows total).
This means:

- Adding a `_sql_constraints` uniqueness rule today would fail `ALTER TABLE` on the very
  next `./upgrade.sh`/deploy, since the existing duplicate rows already violate it.
- It's unknown whether these 21 duplicates have already caused visible side effects —
  `_ems_sync_attendance_template_remove`/`_ems_sync_grade_session_remove` (both called from
  `unlink()`) operate per-triple, so a duplicate row could plausibly have double-created an
  attendance template or grade session line for the affected students, or masked one
  half being silently orphaned on a later single-row delete.

## Open questions (need an answer before touching the code)

1. Were these 21 duplicates created by a single historical bug (e.g. a since-fixed import
   script, a race condition in bulk enrollment) or are they still actively being created by
   something in the current codebase? Worth checking `create_date`/`create_uid` on the 42
   affected rows to see if they cluster around one event or one action, or one automated
   creation path (e.g. `sale.order._ems_apply_destination_placement()`,
   `models/enrollment/enrollment.py`, which creates `ems.enrollment` rows on confirmation —
   does it already guard against duplicates itself? Check `exists = Enrollment.search_count(...)`
   in that method before assuming it's the source).
2. For each of the 21 duplicate pairs: are both rows identical in every other field, or do
   they differ (e.g. different `create_date`, suggesting one is a genuine re-creation after
   the first was somehow not properly removed)? This determines whether deduplication is a
   safe "just keep the oldest/newest" operation or needs a case-by-case look.
3. Did any of the 21 pairs cause a real double-created attendance template or grade session
   row downstream? Cross-check against `ems_attendance_template`/`ems_grade_session` for
   those student/group/subject combinations before deciding whether cleanup is purely a
   dedup of `ems_enrollment` itself or also needs to touch its dependents.
4. Once the data is clean (or the duplicates are confirmed harmless and removable): is a
   plain `_sql_constraints` unique triple the right fix, or does the actual business rule
   need to be scoped differently (e.g. unique per *academic year* rather than globally,
   if a student can legitimately retake a subject in a later course)?

## Where this is also documented

`docs/en/developers/contacts/enrollment.md` — the "Real, deliberately-NOT-fixed gap found"
section — stays even after this plan file is deleted; update it if the resolution differs
from what's written there today.

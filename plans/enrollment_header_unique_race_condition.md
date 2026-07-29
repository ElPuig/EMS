# PLAN — Enrollment uniqueness-per-course is only a Python constraint, not a DB one

> **Status: flagged during the `models/enrollment/enrollment.py` (sale.order header) DTON
> pass (2026-07-28), not implemented.** This is not a design for new work — it's an open
> question for whoever owns the enrollment confirmation flow to answer before any fix is
> written. Nothing below has been built. Verify file/line references against current code
> before acting, since the branch may have moved on since this was written.
>
> Lives under `plans/` per `CLAUDE.md`'s "Design plans" convention — delete this file once
> the question is resolved (fixed, or explicitly decided as intentional and documented in
> `docs/en/developers/enrollment/enrollment.md`).

## Problem

`sale.order._check_unique_enrollment_per_course` (`models/enrollment/enrollment.py`,
`@api.constrains('partner_id', 'ems_course_id', 'state')`) is the only guard preventing the
same student from having two non-cancelled enrollments in the same academic year:

```python
@api.constrains('partner_id', 'ems_course_id', 'state')
def _check_unique_enrollment_per_course(self):
    for order in self:
        if order.state == 'cancel' or not order.partner_id or not order.ems_course_id:
            continue
        domain = [
            ('id', '!=', order.id),
            ('partner_id', '=', order.partner_id.id),
            ('ems_course_id', '=', order.ems_course_id.id),
            ('state', '!=', 'cancel')
        ]
        existing_enrollment = self.search(domain, limit=1)
        if existing_enrollment:
            raise ValidationError(_(
                "The student %(student)s already has a pre-enrolment or "
                "active enrolment for the academic year %(course)s.",
                student=order.partner_id.name, course=order.ems_course_id.display_name,
            ))
```

This is a Python-level `search()`-then-raise check, not a database constraint
(`_sql_constraints`/partial unique index). Two concurrent transactions can each run the
`search()` before either has committed its own new row — both see zero existing
enrollments, both pass the check, both commit, and the student ends up with two live
enrollments for the same course.

## What this means concretely

A classic TOCTOU (time-of-check-to-time-of-use) race. The realistic trigger isn't a
malicious actor — it's ordinary concurrent usage: a secretary and a tutor (or two
secretaries) both creating/confirming an enrollment for the same student within the same
narrow window, e.g. via the `ems.enrollment_proposal_wizard`'s bulk creation racing against
a portal confirm, or two browser tabs open on the same student. How likely this is in
practice depends on real request concurrency in this deployment — worth checking whether
it's ever actually been observed (e.g. via a report or manual query for students with
multiple non-cancelled `sale.order`s in the same `ems_course_id`) before deciding urgency.

## Open questions (need an answer before touching the code)

1. ~~Has this race condition ever actually produced a duplicate enrollment in production?~~
   **Checked 2026-07-29:**
   `SELECT partner_id, ems_course_id, count(*) FROM sale_order WHERE state != 'cancel' AND
   ems_course_id IS NOT NULL GROUP BY partner_id, ems_course_id HAVING count(*) > 1` returns
   **0 rows** — this race has never actually produced a duplicate in this production data.
   Lowers urgency: the gap is real (still a TOCTOU with no DB-level guard) but not an active
   data-integrity incident, unlike `enrollment_junction_duplicate_constraint.md`'s 21 already-
   existing dup triples. Re-run this query before deciding whether/when to fix, since it can
   go stale.
2. If a DB-level fix is warranted: a plain unique index on `(partner_id, ems_course_id)`
   won't work directly, since cancelled orders must be excluded — this needs either a
   **partial unique index** (`CREATE UNIQUE INDEX ... WHERE state != 'cancel'`, expressed in
   Odoo via `_sql_constraints` isn't directly possible for a *partial* index; would need a
   raw SQL migration/`init()` hook instead) or a different modeling approach entirely.
3. If a partial unique index is added: what should happen on the (currently
   `ValidationError`-mediated) conflict at the *database* level instead — does the calling
   code need updating to catch an `IntegrityError`/`psycopg2.errors.UniqueViolation` and
   translate it into the same friendly message, or is a raw DB error acceptable for what
   should be a vanishingly rare race?

## Where this is also documented

`docs/en/developers/enrollment/enrollment.md`, "Uniqueness: one active enrollment per
student per course" section — stays even after this plan file is deleted; update it if the
resolution differs from what's written there today.

# PLAN — `_ems_sync_grade_session_remove` can wipe grades for a still-enrolled student

> **Status: found 2026-07-30 while investigating `plans/enrollment_junction_duplicate_constraint.md`
> (the `ems.enrollment` duplicate-triple cleanup), not implemented.** Not a design for new
> work — a latent bug found by inspection, not yet fixed. Nothing below has been built.
> Verify file/line references against current code before acting, since the branch may have
> moved on since this was written.
>
> Lives under `plans/` per `CLAUDE.md`'s "Design plans" convention — delete this file once
> the fix lands (or is explicitly decided against) and reflected in
> `docs/en/developers/contacts/enrollment.md`.

## Problem

`ems.enrollment.unlink()` (`models/contacts/enrollment.py:52-65`) fires two sync hooks after
deleting a row, both keyed by `(student_id, group_id, subject_id)` — not by the deleted row's
own id, since more than one `ems.enrollment` row can (today, illegitimately — see the
duplicate-constraint plan above) or could (legitimately, if a future feature ever allows it)
share the same triple:

```python
def unlink(self):
    ...
    snapshots = [(enrollment.student_id.id, enrollment.group_id.id, enrollment.subject_id.id) for enrollment in self]
    res = super().unlink()
    for student_id, group_id, subject_id in snapshots:
        self._ems_sync_attendance_template_remove(student_id, group_id, subject_id)
        self._ems_sync_grade_session_remove(student_id, group_id, subject_id)
    return res
```

`_ems_sync_attendance_template_remove` (line 79) correctly guards against this:
```python
still_enrolled = self.search_count([
    ('student_id', '=', student_id),
    ('subject_id', '=', template.subject_id.id),
    ('group_id', 'in', template.group_ids.ids),
])
if not still_enrolled:
    template.student_ids = [(3, student_id)]
```

`_ems_sync_grade_session_remove` (line 102) has **no equivalent check** — it unconditionally
deletes the student's grade lines for any open session matching that group+subject the moment
*any* `ems.enrollment` row for that triple is unlinked:
```python
@api.model
def _ems_sync_grade_session_remove(self, student_id, group_id, subject_id):
    sessions = self.env['ems.grade_session'].search([
        ('group_id', '=', group_id), ('subject_id', '=', subject_id), ('state', '=', 'open'),
    ])
    for session in sessions:
        session.grade_outcome_line_ids.filtered(lambda line: line.student_id.id == student_id).unlink()
        session.grade_subject_line_ids.filtered(lambda line: line.student_id.id == student_id).unlink()
```

## What this means concretely

Today this is only reachable through the (illegitimate) duplicate `ems.enrollment` rows
described in `plans/enrollment_junction_duplicate_constraint.md`: deleting one of a duplicate
pair through the ORM's `unlink()` (with or without `ems_bypass_grade_guard`) would silently
delete the surviving-duplicate student's grade lines for any currently-open session on that
subject/group, even though they remain validly enrolled via the sibling row that wasn't
deleted. This is why that plan recommends a raw SQL delete for the cleanup instead of
`unlink()` — to sidestep this bug rather than rely on it not firing.

Independently of the cleanup, this is a real latent correctness gap in `unlink()` itself: any
future code path that could produce more than one `ems.enrollment` row for the same triple
(even transiently) and then deletes one of them through the ORM would hit the same silent
data loss. Whether that's realistically reachable once the duplicate-triple `_sql_constraints`
(from the sibling plan) is in place is an open question — the constraint would prevent *new*
duplicates from being created at all, which would make this specific trigger path
unreachable going forward, but the asymmetry between the two sync methods is still a bug on
its own terms regardless of whether today's only known trigger gets closed off.

## Open questions (need an answer before touching the code)

1. Fix now (add the same `still_enrolled`-style guard to `_ems_sync_grade_session_remove`,
   mirroring `_ems_sync_attendance_template_remove`), or defer since the
   `enrollment_junction_duplicate_constraint.md` fix (once landed) closes the only known
   trigger path?
2. If fixed: same pattern as the attendance-template guard —
   `search_count([('student_id','=',student_id), ('group_id','=',group_id), ('subject_id','=',subject_id)])`
   before deleting the grade lines. Needs a regression test proving a still-enrolled student's
   grade lines survive a duplicate-row delete (can reuse fixtures from whatever test covers
   `enrollment_junction_duplicate_constraint.md`'s fix, if that lands first).

## Where this is also documented

Not yet documented in `docs/en/developers/contacts/enrollment.md` — add a note there when
this is fixed (or explicitly deferred).

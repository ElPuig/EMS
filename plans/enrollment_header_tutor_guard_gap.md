# PLAN — `_is_blocked_tutor()` doesn't match the real access-control surface

> **Status: flagged during the `models/enrollment/enrollment.py` (sale.order header) DTON
> pass (2026-07-28), not implemented.** This is not a design for new work — it's an open
> question for whoever owns enrollment access control to answer before any fix is written.
> Nothing below has been built. Verify file/line/rule references against current code before
> acting, since the branch may have moved on since this was written.
>
> Lives under `plans/` per `CLAUDE.md`'s "Design plans" convention — delete this file once
> the question is resolved (fixed, or explicitly decided as intentional and documented in
> `docs/en/developers/enrollment/enrollment.md`).

## Problem

`sale.order._is_blocked_tutor()` (`models/enrollment/enrollment.py`) gates
`action_cancel`/`action_quotation_sent`/`action_quotation_send`/`action_send_enrollment_proposal`/
`action_confirm`:

```python
def _is_blocked_tutor(self):
    return (
        self.env.user.has_group('ems.group_teacher') and
        not self.env.user.has_group('ems.group_tutor') and
        not self.env.user.has_group('ems.group_academic_admin') and
        not self.env.user.has_group('ems.group_secretary')
    )
```

This only asks "is the caller a *plain* teacher (not a tutor, admin, or secretary)?" — a
coarse, group-membership-only check. Two layers of the real access-control surface are
narrower than this, and `_is_blocked_tutor()` doesn't know about either:

**1. The `ir.rule` layer is stricter than "is a tutor."** `security/rules/contacts.xml`'s
`rule_sale_order_tutor` only grants write access where
`partner_id.tutor_id.user_id = user.id` **and** `state = 'draft'` — i.e. the caller must be
genuinely *this specific student's* group tutor, not just a member of `ems.group_tutor` in
general. A tutor who belongs to `ems.group_tutor` but isn't *this* student's tutor sails
past `_is_blocked_tutor()` (which only checks group membership) and only gets stopped later
by the `ir.rule` layer — with a bare, less-friendly `AccessError` instead of the
`ValidationError` with a clear message that `_is_blocked_tutor()` produces for a plain
teacher. Inconsistent user experience for what is conceptually the same "you're not allowed
to touch this enrollment" situation.

**2. Cross-study/cross-tutor placement restrictions exist only in the proposal wizard, not
here.** `ems.enrollment_proposal_wizard` (`models/contacts/enrollment_proposal_wizard.py`,
already DTON'd) enforces that a tutor can only propose enrollments for students within their
own scope — see `test_enrollment_placement.py::test_tutor_cannot_cross_study_through_the_orm`,
which already proves the *wizard* blocks this. But `enrollment.py` itself has no
`@api.constrains` (or action-level guard) preventing a tutor from directly writing
`ems_group_id`/`ems_study_id` on an existing `sale.order` outside their own scope via the
ORM/RPC, bypassing the wizard's own checks. Whether the `ir.rule`'s
`partner_id.tutor_id.user_id = user.id` condition already fully closes this gap (since it
gates the whole record's write, not just those two fields) or leaves a narrower hole
(e.g. writing fields on an enrollment the tutor legitimately can write for other reasons)
wasn't fully traced during this pass — needs a closer look.

## Open questions (need an answer before touching the code)

1. Should `_is_blocked_tutor()` be extended to also check "is this genuinely the student's
   own tutor" (mirroring the `ir.rule`'s condition), so a wrong-student tutor gets the
   friendlier `ValidationError` instead of falling through to `ir.rule`'s `AccessError`? Or
   is relying on the `ir.rule` layer as the real enforcement (with `_is_blocked_tutor()`
   only as a UX nicety for the common "plain teacher" case) an acceptable, intentional
   division of labor?
2. Does `enrollment.py` need its own `@api.constrains` mirroring the proposal wizard's
   cross-study/cross-tutor scope check, or is the `ir.rule`'s per-student-tutor condition
   (combined with the wizard being the only realistic UI entry point for setting
   `ems_group_id`) already sufficient in practice? Worth an explicit trace of every code
   path that can set `ems_group_id`/`ems_study_id` on an existing order (direct form edit,
   RPC, the wizard, the transition wizard's bulk placement) before deciding.
3. If a fix is warranted: does it belong in `_is_blocked_tutor()` (Python-level, friendlier
   errors) or as a new `ir.rule` refinement (DB-level, closes the gap regardless of entry
   point but keeps the less-friendly `AccessError`) — or both?

## Where this is also documented

`docs/en/developers/enrollment/enrollment.md`, "Tutor-blocking guards" section — stays even
after this plan file is deleted; update it if the resolution differs from what's written
there today.

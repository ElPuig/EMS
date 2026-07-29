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

## Code-path trace (done 2026-07-29)

Every write site for `ems_group_id`/`ems_study_id` on an existing `sale.order`:

- **`enrollment_form.xml`** (`view_order_form_inherit_ems_enrollment`): both `ems_study_id`
  and `ems_group_id` are plain, directly-editable fields in the form — no `readonly`
  attribute tied to state or to who's editing, beyond whatever `sale.view_order_form`
  itself already applies (the standard "locked once confirmed" behavior, not a tutor-scope
  restriction). While the order is in `draft`, any user with write access to the record —
  including, per `rule_sale_order_tutor`, the student's own assigned tutor — can set
  `ems_group_id` to **any** group directly in the form, with no server-side check that it
  belongs to the same study, level, shift, or course as the enrollment.
- **`_onchange_ems_study_id`** (line 314) clears `ems_group_id` when the study changes, and
  **`_onchange_ems_group_id`** exists alongside it — but both are `@api.onchange`, which is a
  client-side UI convenience only. Neither runs on a direct `write()`/RPC call, and neither
  is backed by an `@api.constrains`.
- **The only `@api.constrains` in the whole file** is `_check_unique_enrollment_per_course`
  (line 386) — there is no constraint anywhere tying `ems_group_id.study_id` to
  `ems_study_id`, or restricting `ems_group_id` to the tutor's own scope.
- **`_ems_fill_suggested_group`**/`action_suggest_destination_group`
  (`models/contacts/contact.py:342`, button in `no_destination.xml`) is the other write path
  — it only fills a group when the enrollment currently has none (`if order.ems_group_id:
  continue`), using `_ems_suggest_group()`'s own study/shift-matching logic, so it can't
  itself introduce a cross-study group. Not part of the gap.
- **`ems.enrollment_proposal_wizard`** enforces cross-study/cross-tutor scope, but only
  within its own `ems_group_id` field on the *wizard* — this has no bearing on what can be
  written directly to an existing `sale.order` afterwards.

**Conclusion: the gap is confirmed, not theoretical.** A tutor who is genuinely the
assigned tutor of a given student, editing that student's own `draft` enrollment (a
completely ordinary, legitimate action `ir.rule` allows), can set `ems_group_id` to a group
belonging to a *different* study/level/shift than the enrollment itself — the wizard's
placement logic is bypassable simply by editing the confirmed order's form directly instead
of going through the wizard, and no `@api.constrains` catches the mismatch. This is separate
from (and narrower than) the "wrong student's tutor" scenario question 1 below is about.

## Open questions (need an answer before touching the code)

1. Should `_is_blocked_tutor()` be extended to also check "is this genuinely the student's
   own tutor" (mirroring the `ir.rule`'s condition), so a wrong-student tutor gets the
   friendlier `ValidationError` instead of falling through to `ir.rule`'s `AccessError`? Or
   is relying on the `ir.rule` layer as the real enforcement (with `_is_blocked_tutor()`
   only as a UX nicety for the common "plain teacher" case) an acceptable, intentional
   division of labor?
2. ~~Does `enrollment.py` need its own `@api.constrains` mirroring the proposal wizard's
   cross-study/cross-tutor scope check~~ **Confirmed above: yes, this hole is real** — the
   `ir.rule`'s per-student-tutor condition only gates *who* can write to the record, not
   *what values* they can write into `ems_group_id`/`ems_study_id`. Remaining question is
   just the fix shape (see 3 below), not whether the gap exists.
3. If a fix is warranted: does it belong in `_is_blocked_tutor()` (Python-level, friendlier
   errors, question 1's concern), as a new `@api.constrains('ems_group_id')` checking
   `ems_group_id.study_id == ems_study_id` (closes the cross-study hole confirmed above,
   regardless of entry point), or both? The `@api.constrains` seems like the clear, low-risk
   fix for the confirmed hole specifically — narrow, mirrors an invariant the onchange
   already assumes should always hold, doesn't touch the separate "friendlier error message"
   question. Recommend doing that piece; the `_is_blocked_tutor()` UX question (1) is
   independent and can wait for a separate decision.

## Where this is also documented

`docs/en/developers/enrollment/enrollment.md`, "Tutor-blocking guards" section — stays even
after this plan file is deleted; update it if the resolution differs from what's written
there today.

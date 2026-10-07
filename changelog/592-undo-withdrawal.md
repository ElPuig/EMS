# What's new

## Undo a withdrawal registered by mistake (Undo withdrawal action on the student form):

- New "Undo withdrawal" entry in the student form's Actions dropdown, for the same roles that register withdrawals (secretary, Head of Studies/Deputy/Director, academic admin). Prompted by a real case: a CFGS student withdrawn on 21/09 instead of his sibling with an almost identical name; unarchiving the contact (the only thing that could be tried) left him as a withdrawal with no group, out of every roll-call.
- Only offered for a withdrawal (never an expulsion) of the current course, when the student has a confirmed enrollment of that course with a group; `res.partner._ems_withdrawal_undo_order()` decides it and `action_undo_withdrawal()` re-checks it and the role server-side (`can_undo_withdrawal`, non-stored, `depends_context('uid')`). A graduate withdrawn afterwards (contact_type alumni, exit_type withdrawal) qualifies too.
- What it does: the course's year record frozen by the withdrawal goes back to provisional when it holds convalidated subjects (only those kept) or is deleted otherwise, and any grades it froze are listed in a chatter note for the teachers to enter again (`ems.student.year_record._ems_reopen_after_undone_withdrawal()`); `_ems_convert_to_student()` reactivates the contact (Google Workspace: scheduled suspension cancelled / account reactivated by the existing write hook); `sale.order._ems_apply_destination_placement()` restores group, study, level and subject enrollments (and with them attendance rosters and open grade sessions); the portal is granted to the same recipients as a new enrollment (student, plus family while a minor) via the new `res.partner._ems_grant_student_portal()`.
- Not recovered (documented in the manual): attendance deleted by the withdrawal, roll-calls taken meanwhile, and draft/sent enrollments the withdrawal cancelled.
- Verified against a copy of the production database (dump of 2026-10-07): the affected student goes back to AD1A with 11 subject enrollments and 26 attendance rosters, the 26-27 "withdrawn" year record removed, portal access back, sibling untouched.
- Secretary manual (ca/es/en) has a new "Undo a withdrawal registered by mistake" section; developer doc `exit_wizards.md` documents the flow.

# Internal changes

## Shared helpers for exit permissions and portal grant/revoke:

- The withdrawal wizard's role check moved to `res.partner._ems_user_can_register_exits()`, shared with the undo action.
- `_ems_revoke_student_portal()` and the new grant helper share `res.partner._ems_apply_portal_access(mode, summary)` (sudo path of `ems.portal.access.wizard._apply_one()`, failures collected as issues instead of raised).

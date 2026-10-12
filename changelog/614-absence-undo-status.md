# What's new:

## Absences: any decision can be undone, one step at a time (issue #614):
- New "Undo the last decision" action, in the form's Actions menu and as an icon at the end of
  the row in the managers' list, asking for confirmation first. Approved goes back to Pending
  Direction, that to Pending validation (or to Pending when the type requires no document), and
  the Head's acknowledgement back to Pending. A refused or cancelled request, or one whose
  document was sent back, returns to the status it had just before.
- Who can undo follows who decided: the Head (Head of Studies, Deputy, Secretary) their own
  decisions, Direction the Head's and its own, the administrator any. Nobody undoes a decision
  on their own absence, except Direction and the administrator.
- Undoing the Head's acknowledgement takes the absence out of the calendar, the hour balance and
  the guard duty board until it is acknowledged again. The employee is always told, and the
  department's chiefs too when the absence goes in or out of effect.
- New `hr.leave.ems_decision_before` (what a refusal, cancellation or send-back replaced) and
  `ems_can_undo`. No migration: a request refused before this simply goes back to Pending.

# Changes:

## Absences: "Direction: pending" and Odoo's "Reset" are gone, replaced by Undo:
- Direction's "Direction: pending" button and Odoo's own "Reset" (which only the administrator
  could use, on refused or cancelled requests) are removed. An employee can no longer reopen a
  request they cancelled themselves: their Head or Direction undoes it.
- Refusing is no longer final, and its confirmation dialog no longer says so.

## Absences: every action of the request form is in its "Actions" dropdown:
- Validate, Received, Validate documentation, Documentation insufficient, Direction: done,
  Refuse, Cancel and Undo are entries of the header's Actions dropdown instead of loose buttons,
  Odoo's own included, following the project's rule for form headers. The list keeps its row
  icons.

# Fixes:

## Absences: the type of an approved request looked editable but could never be saved:
- Odoo refuses any change touching the dates of a request in effect, and changing the type
  recomputes them, so correcting the type of an approved absence always ended in an error. The
  field is now read-only once approved, and the manuals explain the way to correct one: undo the
  approval, correct it and validate it again.

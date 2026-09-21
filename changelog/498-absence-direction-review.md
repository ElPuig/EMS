# What's new:

## Staff absences approved twice, by the Head and by Direction, in either order:
- Every absence now carries three statuses: the Head's decision (`ems_head_state`: Pending /
  Approved / Refused, computed from Odoo's own `state`), Direction's (`ems_direction_state`, the
  former "Direction check", now Pending / Missing document / Done / Refused) and an overall one
  combining both (`ems_status`: Pending, Pending Head, Pending Direction, Pending Document,
  Approved, Refused, Cancelled). Both new fields are stored computes, so existing absences got
  their values on upgrade with no migration.
- Odoo's own `state` is untouched and stays the Head's decision: the absence takes effect
  (calendar leave, hour balance, guard duty board) when the Head approves, as before.
- Direction has its own buttons (done / missing document / back to pending / refuse) in the form
  header and, as icons, beside its column in the list. Refusing from Direction refuses the whole
  request, asks for confirmation and is final, like the Head's refusal.
- Direction no longer gets the Head's Approve/Refuse on somebody else's request (`can_approve`
  overridden for `ems.group_director` except where the Director is the approver, i.e. the Area
  Managers' own absences), so it cannot decide on the Head's behalf by accident.
- Direction's "Waiting For Me" in Management > Absences lists what it still owes: every live
  request whose Direction status is Pending or Missing document, whether or not the Head has
  decided, plus the absences it approves itself as the Head. The left search panel filters by the
  overall status.
- Taking a decision from an absence's form (the Head's Approve/Refuse or any of Direction's
  buttons) goes back to the list it was opened from (`ems_absence_form` js_class, native
  `historyBack()`); an error or a cancelled confirmation stays on the form.
- Direction is subscribed to the request, and so receives the outcome summary, whenever a Head
  approves an absence (any area, including ASP). The summary now shows the overall status.
- Developer doc, Head of Studies / teachers / secretary manuals (ca/es/en) and ca/es translations
  updated; new tours `ems_absence_direction_review` and `ems_absence_head_approval`.

# Related with:
- Closes #498

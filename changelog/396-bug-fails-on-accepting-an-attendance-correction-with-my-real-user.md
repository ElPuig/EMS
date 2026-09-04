# Fixes

## Accepting an attendance correction request crashes (AttributeError on original check-in/out):

`ems.attendance_correction.create()` resolved `attendance_id` from `vals.get("attendance_id")`
before snapshotting `original_check_in`/`original_check_out` from the linked `hr.attendance`
record. The "Request Correction" button's field is `readonly="1"` in the form, so it is only
ever populated via the button's `default_attendance_id` context - the web client never sends it
explicitly in the create payload. Odoo only merges `default_` context values into `vals` inside
the base `create()` (`_add_missing_default_values`), which runs *after* this model's own
override, so the override was browsing an empty `hr.attendance` recordset and silently
snapshotting both original times as `False`. Any later `action_accept()` on that request then
crashed with `AttributeError: 'bool' object has no attribute 'astimezone'` while trying to anchor
the requested time on the (missing) original date.

Fixed by falling back to `self.env.context.get("default_attendance_id")` when `attendance_id`
isn't yet in `vals`. Confirmed against the real production backup: exactly one correction request
existed (created the same day this was reported), reproducing the bug with both original fields
NULL despite a valid underlying attendance record; backfilled from the attendance's own
check-in/check-out and successfully accepted end-to-end as the reporting Head of Studies user.

Added regression coverage for both the unit-level create() path (explicit
`default_attendance_id` context, no `attendance_id` key in vals) and the real browser flow
(`test_attendance_correction_request_tour.py` now asserts `original_check_in`/`original_check_out`
match the attendance after the tour's save).

Version bumped to 18.0.0.23.2 and a `migrations/18.0.0.23.2/post-migrate.py` added, backfilling
any `ems.attendance_correction` row still carrying a NULL `original_check_in`/`original_check_out`
from its (still-linked, `ondelete="cascade"`) `attendance_id` - this reaches production's own
pre-existing broken row (and any archived request too, via `active_test=False`) once this version
is deployed there. Verified against a freshly-created row simulating the pre-fix bug: `./upgrade.sh`
correctly backfilled it and left the already-correct row (Óscar's, fixed manually earlier this
session) untouched.

# Internal changes

## Teacher manual for taking attendance (daily roll-call and guard mode):

The teacher docs index listed "Attendance: management of attendance sessions and guard mode" as a
planned/pending topic even though the feature itself (the **Current** roll-call screen: session
vs. planned-slot selection, marking statuses, notes, strikes, guard mode, deleting a session, and
the read-only **History** list) has been shipped and stable for a while. Added the missing manual
in all three languages (`docs/{en,ca,es}/teachers/attendance-session.md`) and removed the stale
"planned topic" line from each teachers `index.md`.

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

## Starting a covered session in Guard mode leaves the roll-call screen blank:

Clicking "Start session" on a colleague's not-yet-started slot while in Guard mode created the
session and loaded its students correctly, but the screen immediately rendered "No sessions or
scheduled timetables for this day" instead of the roll-call table - the student data had loaded
into memory, it just never got shown. Root cause: the instant a guard-covered session is
started, its `session_teacher_id` becomes the covering teacher's own employee (by design - it
records who actually ran it), which is exactly the condition `get_guard_sessions()` uses to
exclude it (it now belongs to Normal/Manual mode's view instead, to avoid showing it twice).
`onStartSession()` reloads the mode's session/planned lists *before* re-selecting the new
session and loading its lines directly, and the roll-call view's own "nothing at all" empty
state only looked at those (now guard-mode-empty) lists, never at whether the just-loaded
student table actually had rows - so it always won the race and hid a screen that had, in fact,
already loaded correctly. Fixed in `attendance_session_view.xml`'s empty-state condition to also
check for already-loaded lines. Caught by new browser tour coverage for Guard mode (see the
"Internal changes" section) - no existing `TransactionCase` test or clean `upgrade.sh` could
have caught this, since it's purely about what actually renders after a specific reload sequence.

# Internal changes

## Teacher manual for taking attendance (daily roll-call and guard mode):

The teacher docs index listed "Attendance: management of attendance sessions and guard mode" as a
planned/pending topic even though the feature itself (the **Current** roll-call screen: session
vs. planned-slot selection, marking statuses, notes, strikes, guard mode, deleting a session, and
the read-only **History** list) has been shipped and stable for a while. Added the missing manual
in all three languages (`docs/{en,ca,es}/teachers/attendance-session.md`) and removed the stale
"planned topic" line from each teachers `index.md`. Added a short "For Administrators" section to
the same manual pointing at the two Admin docs that already cover everything admin-specific about
this screen (schedule/template setup, status list configuration) - no new admin-only behaviour
exists here beyond those two existing configuration screens.

## Browser tour coverage for the roll-call screen's continuation and guard-mode flows:

Two real, previously untested interactions on the "Current" pass-list screen: the same-day
continuation (double period) auto-copy + its banner, and Guard mode (covering a colleague's
not-yet-started slot, marking it through the separate `write_guard_session_line` RPC, and
confirming no delete option is offered there). Added `tests/test_attendance_session_tour.py` +
`static/tests/tours/attendance_session_tour.js` (2 tours). Along the way, this surfaced the real
bug fixed above, and also a (non-bug) gotcha worth documenting: Guard mode has no "Manual"-style
date/time override of its own - both its RPC calls (`get_guard_sessions`/`get_guard_planned`)
always filter down to whatever matches the real wall-clock time, unlike every other mode - the
fixture's guard slot needed the same "spans the whole day" trick already used by
`test_strike_tour.py`/`test_attendance_passlist_tour.py` to stay deterministic regardless of when
the test actually runs.

## Fixed a pre-existing, environment-dependent test flake in TestAttendanceStatusTour:

Unrelated to this branch's own work, but found and fixed along the way (developer's own call,
rather than papering over it at the `devel.sh` level - see reasoning below): this test logs in
as the real `admin` account and asserts on literal English status text ("Attended"). It fails on
any dev box where admin's own language isn't `en_US` (confirmed on this box: `ca_ES`) - it
presumably only ever passed because a clean install's `admin` defaults to `en_US`. Considered
forcing admin's language in `devel.sh` instead, but rejected: that script is scoped to
production-restore *safety* (email neutralization, debug mode, stuck jobs), not test
determinism, and would also silently change the language the developer sees when manually
exploring a restored dev box every time. Fixed at the actual source instead: the test now forces
`admin`'s language to `en_US` for its own scope only (`self.addCleanup` restores the original
value, on top of the test's own transaction rollback already doing so) - same self-contained
pattern `mock_outgoing_email` already uses elsewhere in this test suite.

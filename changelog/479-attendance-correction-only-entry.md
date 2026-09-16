# What's new:

## Attendance correction hides check-out while the teacher is still clocked in and on schedule:
- When a teacher requests a correction on an attendance where they've checked in but not yet checked out, the "Request Correction" form now only asks for the check-in time if they're still within their expected working hours for that day - there's nothing to correct for check-out yet since they haven't left. Once their scheduled working day for that date has ended (or there was no schedule at all that day), the check-out field appears again as before.
- New `ems.attendance_correction.is_check_out_requestable` computed field drives this, reusing the same "last expected working hour" calculation the auto-checkout cron already relies on (so approved absences and split shifts are handled consistently). The server also strips any check-out value a stale/tampered request might still send while it isn't requestable, on top of hiding it in the form.
- Added a browser tour covering the hidden-field scenario, alongside the existing backend test coverage.

# Fixes

## Attendance correction tests were flaky right around local midnight (found during the close review):
- The "still on schedule" fixtures compared a schedule ending near local (Europe/Madrid) midnight against a freshly-read wall clock, so whenever the suite happened to run in the roughly two-hour window after local midnight, the schedule was correctly judged as already over - failing tests that expected it to still be open. Confirmed reproducing 2026-09-16.
- Fixed by freezing the reference "now" the tests use to a fixed moment, removing the wall-clock dependency entirely, instead of relying on the schedule slot spanning "almost the whole day."

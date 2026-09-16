# What's new:

## Attendance correction hides check-out while the teacher is still clocked in and on schedule:
- When a teacher requests a correction on an attendance where they've checked in but not yet checked out, the "Request Correction" form now only asks for the check-in time if they're still within their expected working hours for that day - there's nothing to correct for check-out yet since they haven't left. Once their scheduled working day for that date has ended (or there was no schedule at all that day), the check-out field appears again as before.
- New `ems.attendance_correction.is_check_out_requestable` computed field drives this, reusing the same "last expected working hour" calculation the auto-checkout cron already relies on (so approved absences and split shifts are handled consistently). The server also strips any check-out value a stale/tampered request might still send while it isn't requestable, on top of hiding it in the form.
- Added a browser tour covering the hidden-field scenario, alongside the existing backend test coverage.

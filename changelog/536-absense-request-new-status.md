# Changes:

## Staff absences: supporting document step between the Head and Direction:
- The approval is now sequential (Head, then Direction) instead of two approvals in either order. For absence types that require a supporting document, the Head first acknowledges the request ("Received: pending documentation", status "Awaiting documentation"), and validates the document later ("Validate documentation") once the employee has attached it; only then does Direction review it. The absence still takes effect (calendar, hour balance, guard duty board) as soon as the Head acknowledges it.
- Attaching the supporting document moves the request to "Pending validation" automatically, with no button for the employee. The Head or Direction can send an insufficient document back ("Documentation insufficient"), which returns the request to the employee with a message.
- Every type now requires a supporting document except "Health" and "ATRI" (data/cat/hr.leave.type.csv, native support_document flag).
- New statuses: Awaiting documentation, Pending validation (overall status and Head status). Removed: "Pending Head" (Direction first) and Direction's "Missing document", replaced by the above.
- One activity per step for whoever acts next (employee: attach the document, due the day after the absence; Head: validate it; Director: review it).
- Daily scheduled action reminding the employee (note, every N days, default 1) once the absence is over and the document is still missing, and reporting it once to the Head after M days (default 3). Both configurable in Settings > Staff Absence Settings.
- "Waiting For Me" filters follow the new steps (the Head's includes documents to validate; Direction's lists only what the Head has validated); new "My pending supporting documents" filter for employees.
- Migration (18.0.0.30.2): already-approved requests count as validated by the Head; Direction's former "Missing document" becomes "Awaiting documentation".
- Technical and user documentation (teachers, head of studies/Direction, secretary, admin) and ca_ES/es_ES translations updated.
- Absences list: status and Head status columns widened so the new status names fit.
- The employee's own absence list and form no longer show the Head's and Direction's separate status columns/badges; the overall status tells them where their request stands.

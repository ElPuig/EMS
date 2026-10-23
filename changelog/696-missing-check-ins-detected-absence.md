# What's new:

## Missing check-ins become detected absences, and teachers are reminded to request them:
- "Expected absences" (`ems.absence_pending`) are now "Detected absences", with an Origin column: Informed (entered by hand by a chief, the Head of Studies or their Deputy) or No check-in.
- Once a day is over, the teachers of the areas chosen in the new setting Settings > EMS > Staff Absence Settings > Detected absences who did not check in at all, or checked in after their first lesson had ended, get a detected absence from their first lesson to their last one (or to the check-in time). Nothing for a teacher with no schedule loaded (nothing to compare the check-ins with), on public holidays, on days nobody in the circuit checked in (summer, school holidays the calendar does not know), nor when an absence or a detected absence already covers it. Empty setting = circuit off (the plan is to start with VET only).
- A check-in recorded afterwards (guard duty board's "The teacher is in the classroom", the Head of Studies, a correction) discards the detected absence, or shortens it when the teacher arrived earlier than it said.
- Every detected absence of a teacher in the circuit, informed or not, reminds the teacher at the start of their next working day, with a different message for each origin, every N days (the existing reminder setting), and is reported once, after the existing escalation days, to their own Head of Studies (nearest Head of Studies or Deputy up the hierarchy, else the area's attendance manager, else the administrators) with a note and an activity.
- Teachers can open their own detected absences (read only, without the internal note) from the reminder's link, and request the absence from there with Request the absence, which opens a new absence request already filled in; saving it links both.
- New scheduled action "EMS: Detected absences", every 15 minutes. Measured on the development database with every area in the circuit (121 teachers), cold: one day's detection 0.06 s, the first reminder run of a day 0.4 s, later runs 0.07 s.

# Changes:

## Absence reminders wait for the start of each person's working day:
- The supporting document and ATRI reminders (and the reports to the Head or Direction) no longer go out at whatever time the daily scheduled action ran: the action now runs every 15 minutes and sends each message on the first run after its reader's working day has started, never outside their working hours or on a day they don't work. Somebody with no schedule at all goes by the centre's default schedule framework.
- Reminders and reports are written in their reader's language instead of the scheduled action's.
- The settings "Supporting document reminder" and "Missing supporting document report" are renamed "Absence reminder" and "Absence report", since they now also drive the detected absences.

# Internal changes:

## Shared reminder helpers and first check-in reading:
- `mail.thread._ems_notify()`, `_ems_remind_at_workday_start()` and `_ems_report_at_workday_start()` are shared by `hr.leave` and `ems.absence_pending`; `res.users._ems_workday_started()` caches each user's working day start for one run.
- `hr.attendance._ems_first_check_in_hours()` is shared by the guard duty board's "not checked in" rows and the detection, and leaves out the technical attendances created by Odoo's own absence detection.
- New tests: `TestAbsenceDetection` (23), a teacher tour for detected absences, a workday-start test for the supporting document reminders; `ems.absence_pending` added to the access matrix.

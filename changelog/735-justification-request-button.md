# Changes

## Teacher can answer a detected absence with a check-in correction request:

- A teacher asked to justify a detected absence (or with the absence prepared for them) now gets both options in the form's Actions dropdown: **Request the absence** and, once the absence is over, **Request check-in correction**. Before, the only way to say "I was at the centre" was to ask the Head of Studies by other means.
- It reuses the usual attendance correction request (`ems.attendance_correction`), now linked to the detected absence (`absence_pending_id`). Two scenarios: the teacher has an attendance that day (the first one is preselected, another can be picked) and it is corrected as usual; or they have none, then both times are required (prefilled with the absence's hours) and accepting the request creates the attendance (such a request can't be rejected once accepted: the approver corrects or deletes the attendance).
- Accepting resolves the detected absence as **Check-in corrected** once nothing is missed (a detected one keeps the part still missed, as its review would). The teacher's reminders pause while the request is pending and resume if it is rejected.

## Times typed by hand are read as hours and minutes:

- The requested check-in/out times use a new `ems_time_of_day` widget: `9.15`, `9,15` (the numeric keypad's decimal key in Catalan/Spanish), `9h15` and `915` all mean 9:15. Odoo's `float_time` read them as decimal hours (`13,04` → 13:00, `1304` → 1304 hours, a value found saved in the dev DB). The server now refuses times outside 0-24.
- The **Correct check-in** dialog of a detected absence offers every minute (Odoo's picker only offered multiples of five, so an entry's own hours such as 16:06 got changed) and no seconds.

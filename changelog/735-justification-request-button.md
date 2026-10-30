# Changes

## Teacher can answer a detected absence with a check-in correction request:

- A teacher asked to justify a detected absence (or with the absence prepared for them) now gets both options in the form's Actions dropdown: **Request the absence** and, once the absence is over, **Request check-in correction**. Before, the only way to say "I was at the centre" was to ask the Head of Studies by other means.
- It reuses the usual attendance correction request (`ems.attendance_correction`), now linked to the detected absence (`absence_pending_id`). Two scenarios: the teacher has an attendance that day (the first one is preselected, another can be picked) and it is corrected as usual; or they have none, then both times are required (prefilled with the absence's hours) and accepting the request creates the attendance (such a request can't be rejected once accepted: the approver corrects or deletes the attendance).
- The attendance the request is about is never the teacher's choice (hidden in the dialog, imposed by the server): a real check-in of that day if there is one (e.g. a late arrival), otherwise the red technical attendance Odoo leaves on a day without check-in (the one teachers have always asked to correct), otherwise a new one recorded on acceptance. For a red one, the requested times default to the absence's (also from the classic "Request Correction" on a red attendance, which now proposes the schedule's times instead of 00:00); accepting turns it into a real attendance and rejecting restores it as a red one (rejecting a pending request no longer turns it into a manual attendance either).
- The detected absence's form shows the teacher a blue notice with what is expected of them: request the absence or a check-in correction, send the absence prepared for them, or wait for their correction to be reviewed.
- The two answers exclude each other: while a correction request is pending the teacher can't request the absence (button hidden, refused on the server), and once the absence is requested no correction is offered.
- Accepting resolves the detected absence as **Check-in corrected** once nothing is missed (a detected one keeps the part still missed, as its review would). The teacher's reminders pause while the request is pending and resume if it is rejected.

## Times typed by hand are read as hours and minutes:

- The requested check-in/out times use a new `ems_time_of_day` widget: `9.15`, `9,15` (the numeric keypad's decimal key in Catalan/Spanish), `9h15` and `915` all mean 9:15. Odoo's `float_time` read them as decimal hours (`13,04` → 13:00, `1304` → 1304 hours, a value found saved in the dev DB). The server now refuses times outside 0-24.
- The **Correct check-in** dialog of a detected absence offers every minute (Odoo's picker only offered multiples of five, so an entry's own hours such as 16:06 got changed) and no seconds.
- The teacher's reminder for a missing check-in now tells them to request a check-in correction from the page, instead of asking their Head of Studies to record it. The teacher manual's screenshots show both options and the correction request dialog; the dialog's "Employee" heading was untranslated and is now translated.

## Teachers find their absences to regularize from the Absences menu:

- A new **Absences → Absences to regularize** entry lists the teacher's own detected absences they have been asked to justify (or that were prepared for them), so they don't have to wait for the next morning's reminder to act. Resolved ones leave the list (the default filter can be removed to see them). "Absences" becomes a dropdown for teachers, with My Time Off first; non-teaching staff keep the plain link.

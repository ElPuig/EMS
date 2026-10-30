# Changes

## Teacher can answer a detected absence with a check-in correction request:

- A teacher asked to justify a detected absence (or with the absence prepared for them) now gets both options in the form's Actions dropdown: **Request the absence** and, once the absence is over, **Request check-in correction**. Before, the only way to say "I was at the centre" was to ask the Head of Studies by other means.
- It reuses the usual attendance correction request (`ems.attendance_correction`), now linked to the detected absence (`absence_pending_id`).
- The attendance the request is about is never the teacher's choice (hidden in the dialog, imposed by the server): a real check-in of that day if there is one (e.g. a late arrival), otherwise the red technical attendance Odoo leaves on a day without check-in (the one teachers have always asked to correct), otherwise a new one recorded on acceptance. For a red one, the requested times default to the absence's (also from the classic "Request Correction" on a red attendance, which now proposes the schedule's times instead of 00:00); accepting turns it into a real attendance and rejecting restores it as a red one (rejecting a pending request no longer turns it into a manual attendance either).
- The detected absence's form shows the teacher a blue notice with what is expected of them: request the absence or a check-in correction, send the absence prepared for them, or wait for their correction to be reviewed.
- The two answers exclude each other: while a correction request is pending the teacher can't request the absence (button hidden, refused on the server), and once the absence is requested no correction is offered.
- The detected absence's status bar shows the steps each entry really went through, ending in its state (e.g. To review → Justification requested → Check-in corrected, or To review → Absence prepared → Requested), with the review step hidden from the teacher. A fixed list of steps showed "Requested" after **Check-in corrected** as if it were the next step, and "Justification requested" on prepared absences. New `ems_statusbar_path` widget (the native status bar fed by a computed `status_path`).
- Rejecting a still pending correction request of a red attendance no longer turns it into a manual one (Odoo switches a technical attendance to manual whenever its times are written).
- An absence the teacher files from My Time Off while their correction waits withdraws it (rejected on its own, no approver, task closed) and links the detected absence as usual.
- Chiefs, Heads of Studies and the Director only read and regularize their own detected absences, like any teacher (they could edit their dates before): hierarchy rule split into read and change, the teacher's own rule made read-only. "Absences to regularize" offers no New button.
- The teacher's correction dialog hides the status bar and the Decision section while the request is being written.
- Accepting resolves the detected absence as **Check-in corrected** once nothing is missed (a detected one keeps the part still missed, as its review would). The teacher's reminders pause while the request is pending and resume if it is rejected.

## A detected absence is claimed again whenever what resolved it falls through:

- A detected absence exists to claim one of the teacher's two duties: requesting the absence or a check-in correction. Whichever way that request comes, it resolves the entry; if it falls through, the entry goes back to the Head of Studies' review ("To review", with a new task and a note saying why; the teacher hears nothing until asked again).
- Reopened when its absence request is refused, cancelled, deleted or moved to other days (undoing the refusal links it again), and when its check-in correction is rejected, also after having been accepted (the attendance is restored, or deleted if the correction recorded it: such a correction can now be rejected).
- An absence request filed beforehand kept its days out of the detection; refused or cancelled, those past days are detected then for that teacher (only days the detection had already gone through).
- A correction asked for from the attendance itself (the classic "Request Correction", e.g. on the red one) now answers the detected absence of that day like the button does: reminders paused, off the review, resolved on acceptance.
- Partial coverage: an absence request or a correction covering only part of a detected absence resolves that part (it keeps the entry, so a later refusal or rejection reopens only it); what still holds a schedule period stays claimed.
- Two new statuses close each way out: **Justified** once the absence request is approved for good (back to Requested if the approval is undone; Requested now means "being dealt with"), and **Correction requested** while the teacher's check-in correction waits for a decision (instead of Justification requested plus a hidden flag). Both are in the status bar, the list, the filters and the default views.
- Migration 18.0.0.42.1 reopens the detected absences whose absence request was refused, cancelled or deleted before this version, and marks as Justified those whose request is already approved.
- The technical documentation has the whole circuit as a flowchart.

## Times typed by hand are read as hours and minutes:

- The requested check-in/out times use a new `ems_time_of_day` widget: `9.15`, `9,15` (the numeric keypad's decimal key in Catalan/Spanish), `9h15` and `915` all mean 9:15. Odoo's `float_time` read them as decimal hours (`13,04` → 13:00, `1304` → 1304 hours, a value found saved in the dev DB). The server now refuses times outside 0-24.
- The **Correct check-in** dialog of a detected absence offers every minute (Odoo's picker only offered multiples of five, so an entry's own hours such as 16:06 got changed) and no seconds.
- The teacher's reminder for a missing check-in now tells them to request a check-in correction from the page, instead of asking their Head of Studies to record it. The teacher manual's screenshots show both options and the correction request dialog; the dialog's "Employee" heading was untranslated and is now translated.

## Teachers find their absences to regularize from the Absences menu:

- A new **Absences → Absences to regularize** entry lists the teacher's own detected absences they have been asked to justify (or that were prepared for them), so they don't have to wait for the next morning's reminder to act. Resolved ones leave the list (the default filter can be removed to see them). "Absences" becomes a dropdown for teachers, with My Time Off first; non-teaching staff keep the plain link.

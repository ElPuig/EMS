# What's new:

## Absences: the requester is told what was corrected in their request, with an optional message (issue #615):
- When the Head or Direction changes the absence type, the dates or the times of a request
  somebody else filed, the next decision on it (acknowledging, validating, validating the
  document, sending it back, Direction's review, refusing) first opens a dialog listing the
  changes, with a box to write a message for the requester. Left blank, the requester is only
  told what was changed.
- The requester receives a single note with the request's new status, the changes and the
  message. It is addressed to them alone: the department's chiefs and Direction, who follow the
  request, do not receive it (which is why the chatter was not an option).
- A correction saved on a request with no decision left (refused or cancelled) is reported to
  the requester straight away, without a message.
- The employee's own edits are not corrections, and a correction that is undone before the
  decision is not reported.
- Deciding from the form still goes back to the list, now also after the dialog.
- New `ems.absence.change_notice_wizard`, `hr.leave.ems_original_request` (no migration: it
  starts empty). Backend tests in `TestAbsenceRequest` and a new tour,
  `ems_absence_change_message`. Manuals updated for Heads of Studies/Direction and teachers.

## Absences: a reason can be given when refusing a request:
- Every Refuse button (the Head's in form, list and kanban, Direction's in form and list) now
  opens a dialog with a box for the reason of the refusal, which is optional. It replaces the
  plain confirmation the buttons had, and when the request had been corrected the same dialog
  also lists the changes: never two dialogs in a row.
- The reason is sent to the requester alone, in the same private note as the changes, and stays
  on the request, shown in red at the top of the form while it is refused. The department's
  chiefs keep receiving only the summary, without the reason.
- New `hr.leave.ems_refusal_reason` (no migration). Reopening a refused request clears it.

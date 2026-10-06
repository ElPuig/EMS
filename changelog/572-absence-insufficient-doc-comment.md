# What's new

## Reason required when an absence's supporting document is sent back (issue #572):

- "Documentation insufficient" (Head validating the document, or Direction reviewing it, from the
  form or the list row) now opens a dialog asking why the document is not valid. The reason is
  required and replaces the old yes/no confirmation.
- The employee gets it in the note telling them to attach a new document, in their "Attach the
  absence's supporting document" activity, and as a warning at the top of the request while it is
  Awaiting documentation (`hr.leave.ems_document_return_reason`, cleared when the document is
  validated or the request is reset). New transient model `ems.absence.document_return_wizard`.
- Sending a new document back again before it is validated opens the dialog with the previous
  reason, to edit instead of writing it from scratch.
- Tests: backend (reason stored, sent to the employee and on the activity; required; offered again on a
  second send-back; cleared on validation and reset), Direction's tour fills in the dialog, new `ems_absence_document_returned` tour for the
  employee's side. ca/es translations and the head of studies, secretary and teachers manuals
  updated in the three languages.

# What's new

## Absence requests can be exempted from their supporting document (issue #634):

- While a request is "Awaiting documentation", the Head who approves it (and, above them, Direction and the administrator) can use "Exempt from supporting document" in the form's Actions menu, after a confirmation, when the document is not going to arrive and is not needed. No reason is asked.
- The request goes on to Direction exactly as if its document had been validated, but the supporting document status is recorded as a new "Waived" value (`ems_document_state = 'waived'`), never "Validated", so lists, filters and the chatter tracking keep a document nobody checked apart from one that was.
- The employee's "attach the document" activity is closed, the daily reminders stop, and the employee gets a note saying the document is no longer required. A reason the document had been sent back with earlier is kept.
- "Undo the last decision" takes a waiver back to "Awaiting documentation" (showing that earlier reason again, if there was one). The change-notice dialog (corrections made by the Head) also opens for this decision.
- Who may waive it is a non-stored `ems_can_waive_document`, re-checked on the server. Covered by backend tests and a new tour run as Head of Studies; developer doc, Head of Studies/secretary/teacher manuals (ca/es/en) and ca/es translations updated.

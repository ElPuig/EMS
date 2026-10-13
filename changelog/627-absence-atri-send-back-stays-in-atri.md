# Fixes

## ATRI absences (insufficient documentation is solved in ATRI, not in EMS):

- An ATRI absence is justified on the Generalitat's portal, but Direction's "Documentation insufficient" sent it to "Awaiting documentation": the employee was asked to attach a file in EMS and the request went through the Head (HOS/DHOS) again.
- On an ATRI absence Direction is reviewing, "Documentation insufficient" now sends it back to "Pending ATRI confirmation", like "Not in ATRI" does, with its own message: the employee is told the documentation in ATRI is not sufficient and why, completes it on the portal and confirms, and the request returns straight to Direction. Both buttons stay.
- The supporting-document send-back is refused server-side on such a request (`_ems_check_can_return_document`), whatever the way in. Other absence types are unchanged.
- Covered by two backend tests and the `ems_absence_atri_document_insufficient` tour; manuals (Head of Studies/Direction, teachers) and the developer doc updated.

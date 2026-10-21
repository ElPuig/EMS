# Changes

## Convalidation requests (oldest first, identity document, academic history tab):

- The backend list of convalidation requests now shows the oldest request on top (registration number ascending), so requests are dealt with first come, first served. The student's own list on the portal keeps showing the newest first.
- The request form shows the student's identity document (DNI/NIE) right under the IDALU, with the same compact copy button and the same width, to look the student up in other applications. It is also an optional list column and can be searched from the Student search field.
- New "Academic history" tab on the request, for the Head of Studies, the Deputy Head of Studies, the Director, the secretariat (who keeps the history) and the administrator: the student's history at the centre, one line per course, the same list the student form shows (now a shared list view). Field-level groups keep it out of reach by RPC for anybody else.
- The circuit's outcome (proposal, Ministry, resolution and registration dates and users, the resolution PDF and the Ministry's own resolution) moved from the top of the form to the "Resolution" tab, next to the comments for the student; the top keeps only what was filed.
- The resolution comments are printed on the resolution PDF when the Director resolves, so they can only change until then (the Director included, right before resolving): from "Pending the secretariat" on they are read-only on the form and refused by the server, so the PDF, the resolution email and the portal always say the same.
- The convalidation tours now look up their own requests by the test course's registration number instead of relying on them being on top of the list.

# Related with

- Closes #657

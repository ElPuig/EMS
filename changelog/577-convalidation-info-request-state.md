# What's new:

## Convalidations: "Pending documentation" state and predefined documentation request reasons:
- Asking a convalidation applicant for more documentation now moves the request to a new
  "Pending documentation" state (from Pending or In process at the Ministry) instead of leaving
  it in Pending. The Deputy Head of Studies' review task leaves their tray meanwhile.
- The request goes back to where it was (Pending, or In process at the Ministry when it was
  filed there) as soon as the applicant answers from the portal, or when the Head of Studies
  marks "Documentation received" for documentation that arrived on paper or by email; the review
  task is scheduled again.
- While waiting, subjects can still be decided but nothing can be proposed or sent to the
  Ministry; the applicant can still cancel it (unless filed with the Ministry).
- The "Request information" wizard now takes a required reason from a configurable catalog
  (Academic management > Configuration > Documentation request reasons), working like the strike
  reasons: translatable name, drag-to-order, archivable, first one preselected. Seeded with
  "Missing official grade certificate from the previous centre" (first, the usual case), missing academic certificate,
  missing syllabus and other. The free text becomes optional "Details". The email and the portal
  show the reason, in the reader's language, followed by the details.
- New list filter "Pending documentation". It is not part of the default filters: those requests
  wait for the applicant, not for the centre.

# Changes:

## Convalidation request form actions moved to the "Actions" dropdown:
- Every header button of the convalidation request form (propose, Ministry, resolve, return,
  register, request information, cancel, reopen...) now lives in the form's Actions dropdown,
  per the project rule for forms touched after it was introduced. Manuals and screenshots
  updated accordingly.

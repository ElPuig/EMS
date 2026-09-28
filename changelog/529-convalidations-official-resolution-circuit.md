# Breaking changes

## Convalidation circuit rebuilt around the official resolution (issue #529):
- Every request is reviewed by the Deputy Head of Studies and stays in their hands until it is
  resolved. It is resolved either by the centre (the review becomes a proposal the Director turns
  into the official resolution PDF, or sends back for review with a reason) or by the Ministry (new
  state "In process at the Ministry"; the Head of Studies records its answer, optionally attaching
  its PDF, and it skips the Director).
- Every resolution, full refusals included, goes through the secretariat, which registers it in
  Esfera and closes the request: completed when something was convalidated, rejected otherwise.
  The whole-request "Reject" button is gone (a refusal is decided subject by subject, with a
  mandatory reason printed on the resolution), and the secretariat no longer changes grades.
- New states: Pending the Director, In process at the Ministry; "In progress" is now "Pending the
  secretariat". New Director task type (holder of the Director position).

# What's new

## Convalidation resolution PDF (issue #529):
- Generated in Catalan when the Director resolves: registration number, applicant and
  representative, study and course, grounds of law (RD 1085/2020, art. 8, plus a text per request
  grounds), one row per module (favourable/unfavourable, "Convalidat" or the grade, reason), the
  Director's signature block with a green "Validat a l'EMS" stamp (who resolved it, date and
  reference; not a legal signature) and the appeal footer.
- Settings: grounds-of-law texts per grounds, the appeal footer and "signed by delegation" are
  configurable (empty = standard text).
- Attached to the resolution email and downloadable from the portal once registered.
- Qualified electronic signature with the Director's certificate is future work (issue #530).

## Who can request convalidations from the portal (issue #529):
- A minor's requests are filed only by the family; a minor with no family contact on file is told
  to fill it in from the profile page. The minor can still follow his own requests.
- An adult files his own, and his family can too when he authorized sharing with it (even though
  the rest of the portal is view-only for that family).
- The resolution email goes to the student and, while a minor or when he authorized sharing, to
  the family too.
- The documentation the Head of Studies asks for is shown on the request's portal card, right
  above the answer form, and on its own tab in the backend form.

# Internal changes

## View-only portal tour fixture actually enables sharing (issue #529):
- The fixture wrote `auth_share` with raw SQL before flushing, so a pending recompute reset it and
  the "family of an adult who shares" tour never really ran that case.

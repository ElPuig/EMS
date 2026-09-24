# Plan: translate `ems.student.document._doc_label()`

**Status: current as of 2026-09-24, not started.** Found while taking the families'
`manual-documentacio.md` screenshots (branch `488-documentation-images-phase-3`). The same bug on
the portal page itself was fixed in that branch; this backend-side instance was left out of scope.

## Problem

`models/contacts/student_document.py::_doc_label()` builds the type label with
`dict(self._fields['doc_type'].selection)`, which is the English source of the selection, never
its translation. It feeds:

- `_compute_name` (the record's display name in the review queue),
- every chatter message body (`create()`, `action_approve()`, `action_reject()`, `action_cancel()`,
  `action_reset_to_pending()`) - the approve/reject/cancel ones are `mt_comment`, so they are
  **emailed to the student/family** as "Document approved: Passport",
- the review task summary (`_schedule_review_activities`).

## Proposed fix

Use the translated labels: `dict(self._fields['doc_type']._description_selection(self.env))`
(the same mechanism `fields_get()` uses). Points to decide before implementing:

- A chatter message is stored once, rendered in whatever language the *acting* user has (the
  secretary approving it), not the recipient's. For a family-facing email that's probably
  acceptable (the centre works in Catalan) but it is a choice, not a given.
- `_compute_name`: check whether `name` is stored; if so, a translated label would freeze the
  language of whoever triggered the recompute - probably keep it untranslated there, or make the
  field non-stored.
- Add a test under a `ca_ES` context, setting the selection translation explicitly (same trick as
  `TestPortalActions.test_documentation_page_translates_selection_labels`) so it does not depend
  on the `.po` being loaded.

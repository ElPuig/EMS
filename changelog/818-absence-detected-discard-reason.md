# What's new

## Detected absences: discard reason (issue #818):

- Discarding a detected absence now opens a dialog asking why, from a catalog of reasons (Strike, Error, Others to start with), plus optional details, like the convalidation refusal reasons. It works the same from the form's Actions dropdown and from the list's action menu for several entries at once.
- The reason and details stay on the entry (shown on the form, an optional list column and a "Discard reason" group-by), visible to the reviewers only: the teacher is still not told, and never sees why (`discard_reason_id`/`discard_details` carry `groups=` Head of Studies, academic administrator, technical administrator).
- The catalog (`ems.absence_pending.discard_reason`, seeded in `data/main/`) is maintained by the Heads of Studies and the academic administrator under Absences > Configuration > Detected absence discard reasons; Absences > Configuration is widened to those two groups, who only see this entry under it. A reason in use is archived, not deleted (`ondelete='restrict'`).

# Fixes

## Strike form label untranslated:

- The student strike form's "Strike" label was shown untranslated in Catalan and Spanish; it now reads "Vaga"/"Huelga" (the same block translates the new "Strike" discard reason).

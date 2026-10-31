# What's new

## Convalidations with a fixed 5 (issue #738):

- A convalidated subject now has a **Grade type** with three options instead of the old "Without grade" checkbox: **With grade** (5 to 10, as before), **Without grade** (plain CV, not counted in the average, as before) and the new **With a fixed 5**, for convalidations that always get a 5 whatever grade the previous studies hold.
- The Head of Studies picks it in the Convalidate dialog (the grade field hides for the two options that need none) and can still change it on the line while the request is under review; like the grade, it is locked once proposed.
- A fixed 5 reaches the student's grades and year record as a 5 and counts towards the average; the resolution PDF and the portal show it as "5 (nota fixada)", the resolution email as "nota fixada: 5" (in each language), and the teachers' notice as "with a fixed 5".
- The form's subject list shows the **Grade type** column, so the secretariat knows how to register each subject in Esfera.
- Manuals updated for the Head of Studies, the secretariat and families (ca/es/en), with new screenshots; developer doc updated.

# Internal changes

## Grade type replaces the "without grade" flag on convalidation lines (issue #738):

- `ems.convalidation.line.without_grade` (Boolean) becomes `grade_type` (Selection `GRADE_TYPES`: `grade` / `without_grade` / `fixed_five`), shared with the grant wizard's `mode`; `_ems_resolved_grade()` returns 5 for `fixed_five`, and the teachers' notice items moved to `_ems_notice_item()`.
- `migrations/18.0.0.43.1/pre-migrate.py` creates and fills `grade_type` from the old column (lines without grade keep it, the rest, NULLs included, become "with grade") and drops `without_grade`. Manifest bumped to 18.0.0.43.1.

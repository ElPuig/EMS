# What's new:

## Previous curriculum records (academic history of a superseded curriculum, issue #672):
- New read-only "Previous curriculum record" (`ems.student.previous_curriculum_record` + `.line`), separate from the per-course academic history: a VET cycle of an earlier law (LOE by units, UF, as SAGA issued it) cannot be mapped onto the current curriculum (different numbering, hours and modules, units instead of learning outcomes, no course per module), so it is kept exactly as printed: curriculum code and name, source application (SAGA), centre, years, attached document, title obtained and its date, and one line per module and unit with hours, grade (text: number, NP, Ap, CV...), sitting and whether it is passed.
- Import wizard from the student form (Actions > Import a previous curriculum record), for the secretariat, academic administration, Head of Studies and Director: uploading the "Historial acadèmic" PDF fills in the header and a review grid with every module and unit; grades and sittings can be corrected; the IDALU must match; the same curriculum cannot be imported twice. The document never says whether the student graduated, so "Title obtained" is proposed when every listed module is passed and confirmed by the user.
- Shown in the student's Studies tab, in the convalidation request's Academic history tab, and in Planning and Grading > Grades > Previous curricula. A previous curriculum title obtained at this centre counts for the convalidation request's "Holds a title obtained at this centre" notice.
- Readable by the whole teaching staff (like the academic history); the secretariat and administration may correct a record, only the administration may delete one.

# Internal changes:

## Shared helpers for academic certificate readers:
- The certificate's IDALU check moved to `ems.base.get_certificate_student_problem()` and the study lookup by code token to `ems.study.find_by_code_token()`, both now used by the Esfera previous record wizard and the new previous curriculum wizard.

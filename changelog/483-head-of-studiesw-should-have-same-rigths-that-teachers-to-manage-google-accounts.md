# Fixes

## Head of Studies and Director can view every student's Google credentials:

- Issue #478 opened the students' Google credentials PDF (Documentation tab and the "Download Google credentials" bulk action) to tutors, limited to their own tutees. Head of Studies and Director inherit the tutor group, but tutor no group themselves, so in practice they saw no credentials at all, same as a plain teacher.
- New read-only record rule `rule_ems_student_document_head_of_studies` (`security/rules/contacts.xml`): Head of Studies (and Director, which implies it) read the Google credentials PDF of every student centre-wide, matching the centre-wide reach they already have on the rest of the student's data. Every other document type (ID card, IBAN, medical card, benefit proof) stays hidden from them; resetting, creating and suspending Google accounts stays with admin/TAC (and secretary for create/suspend).
- Covered by `TestStudentDocumentHeadOfStudiesAccess` and a new run of the tutor credentials tour logged in as a Head of Studies who does not tutor the student. Developer doc, Head of Studies manual index and tutors' credentials manual (ca/es/en) updated.

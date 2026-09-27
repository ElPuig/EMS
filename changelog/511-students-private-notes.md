# What's new

## Private notes (tutoring) on the student's file:
- The student's form now has two notes tabs instead of the native "Internal Notes" one: "Public notes (teachers)" (the same native comment field, read by every teacher) and "Private notes (tutoring)".
- Private notes are only read and written by the student's current tutor, every chief above that tutor in the hierarchy (Seminar/Department Chief, their Head of Studies, the Director, via hr.employee.tutor_scope_user_ids), the Guidance and Coexistence teams and the academic admin. Anyone else never sees the tab, and the field reads empty for them (read/export included).
- Stored in a new model, ems.student.private_note (one per student), reachable directly only by the academic admin; res.partner.private_notes is a non-stored compute whose read/write goes through a single per-student check (_ems_can_access_private_notes). create()/write() store it without requiring write access on the partner, so Guidance and Coexistence can write notes of students they don't tutor.
- Other contact types (families, providers, applicants) keep the native "Internal Notes" tab untouched. The public notes field is now read-only on the form for users who can't save the student anyway (read_only_user), instead of failing on save.
- Each notes tab shows a short, discreet line above the editor stating who can and cannot see those notes. To make that promise hold, the native public notes field (comment) is now restricted to internal users: a portal student or family could previously read their own partner's notes over RPC.
- Backend tests, a tutor/teacher browser tour, a new trilingual manual (teachers, linked from the tutors and head of studies indexes) with a screenshot, and ca_ES/es_ES translations.

# Changes

## Student form redesigned (header in columns, 10 tabs down to 6):
- The Student data tab is gone and the top of a student's form was redesigned to fit above the tabs: two aligned columns next to the photo, first name over the personal email and last name over the corporate email (the name row applies to every person contact), then three columns (Contact, Identification, Personal data) and a single row with the Yes/No summary of the four authorizations. "Adult" now shows a Yes/No badge. A non-tutor teacher now reads both emails, no longer sees the first/last name fields (the name is the title) nor the birth date (the adult badge is enough), and never the personal identifiers.
- Tab order changed: a student's form opens on Schedule, followed by Studies and Contacts & Addresses.
- Translation fix found on the way: several already-translated labels of the student form (authorization/benefit/special-needs badges) had their .po entries left behind when the view was re-indented, which a clean install would have shown in English (this database kept them only because Odoo preserves translations when a view is rewritten). All terms of the form now have a matching .po entry.
- Academic history is now a section at the end of the Studies tab (still the only section former students see).
- The Secretary tab now gathers the administrative lists: authorizations, bonifications and exemptions, the family's uploaded documentation (was its own tab) and the student's bank accounts (was the native Invoicing tab, now hidden for students only).
- Each moved section keeps the exact access groups of its old tab, so nobody sees more than before. Tours clicking the removed tabs now open the tabs that hold those sections.
- User manuals (ca/es/en) updated to the new layout: a new "student's form" section in the secretary's contacts manual with a screenshot of the header, the Documentation and Academic history references pointing to their new place, and every manual screenshot showing the student form regenerated.

# Fixes

## Bonifications and exemptions no longer readable by every teacher:
- Any teacher could read the bonifications and exemptions (family economic data) of every student. They are now read only by admin, secretary, Head of Studies, guidance, coexistence and the student's own tutor and the chiefs above them; the benefits badge on the form stays visible to everyone.
- The Secretary tab hides its Bonifications & Exemptions and Documentation sections from whoever can't read any of them, instead of showing an empty list that looked as if the student had none.

# Related with
- Closes #511

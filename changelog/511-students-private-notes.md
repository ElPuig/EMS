# What's new

## Private notes (tutoring) on the student's file:
- The student's form now has two notes tabs instead of the native "Internal Notes" one: "Public notes (teachers)" (the same native comment field, read by every teacher) and "Private notes (tutoring)".
- Private notes are only read and written by the student's current tutor, every chief above that tutor in the hierarchy (Seminar/Department Chief, their Head of Studies, the Director, via hr.employee.tutor_scope_user_ids), the Guidance and Coexistence teams and the academic admin. Anyone else never sees the tab, and the field reads empty for them (read/export included).
- Stored in a new model, ems.student.private_note (one per student), reachable directly only by the academic admin; res.partner.private_notes is a non-stored compute whose read/write goes through a single per-student check (_ems_can_access_private_notes). create()/write() store it without requiring write access on the partner, so Guidance and Coexistence can write notes of students they don't tutor.
- Other contact types (families, providers, applicants) keep the native "Internal Notes" tab untouched. The public notes field is now read-only on the form for users who can't save the student anyway (read_only_user), instead of failing on save.
- Each notes tab shows a short, discreet line above the editor stating who can and cannot see those notes. To make that promise hold, the native public notes field (comment) is now restricted to internal users: a portal student or family could previously read their own partner's notes over RPC.
- Backend tests, a tutor/teacher browser tour, a new trilingual manual (teachers, linked from the tutors and head of studies indexes) with a screenshot, and ca_ES/es_ES translations.

# Related with
- Closes #511

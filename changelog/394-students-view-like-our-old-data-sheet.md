# Changes:

## Student list view now mirrors the official Esfera data export:
- The list view (not kanban) of the Students screen now shows, by default, columns matching the centre's own official student data CSV as closely as EMS's data model allows: document ID/DNI-NIE, birth date, legal-age status, social security number (NUSS), nationality, street, postal code and city, alongside the existing group/tutor columns.
- Also surfaced the four authorization badges (image rights, school trips, health data, share with family) as list columns, reusing fields already computed for the student form and already used as columns in the tutor-facing list.
- Removed unused columns that don't apply to a student record (State, VAT, Invoice sending method, EDI format, Tags) and fully hid exit-related columns (exit type/course) that aren't part of the reference sheet.
- Every optional column now defaults to visible; any of them can still be hidden per user via the column selector.
- No model changes: every added column reuses a field that already existed on the contact model. Family contact info (phone/email of linked family members) was investigated but deferred — no ready-made field exists for it today, since a student can have more than one linked family contact.

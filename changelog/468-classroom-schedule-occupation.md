# What's new:

## Classroom occupation schedule:
- Added a read-only "Schedule" tab to the space (classroom) form, showing every class booked
  into that room across the whole week (subjects, teachers, breaks that happen to be assigned to
  it), aggregated from the same teacher-calendar data already powering the group's and the
  student's own Schedule tabs — reuses the same OWL widget and PDF-export mechanism.
- Exportable to PDF from the tab's own toolbar (also available from the space form's native
  Print menu), same as the group's/student's own schedule PDF.
- Unlike a group's or a student's schedule, a room's grid always shows the full day (morning and
  afternoon together), since a classroom is routinely booked in both.

# Changes:

## Redesigned the space (classroom) form:
- Reorganized `ems.space`'s form into two rows: code + name on the first row, type + location on
  the second (the `work_location_id` field, previously labeled "Work location", is now labeled
  "Location").
- Added chatter (messages/notes/activities/followers) to the space form via
  `_inherit = ['mail.thread', 'mail.activity.mixin']`.
- A new space now defaults to type "Classroom" and location "Main building" when opened via the
  "New" button, instead of both fields starting empty.
- `ems.space_type`'s `name` field is now translatable (`translate=True`) — the 5 seeded types
  (Classroom, Equipment, Laboratory, Office, Workshop) got real Catalan/Spanish translations
  (`Aula`/`Equipament`/`Laboratori`/`Despatx`/`Taller` in Catalan; `Aula`/`Equipamiento`/
  `Laboratorio`/`Despacho`/`Taller` in Spanish) instead of only ever showing in English.
- `hr.work.location`'s `name` field (native Odoo, not translatable by default) is now
  translatable too, the same way — "Main building" now shows as "Edifici principal"/"Edificio
  principal" in Catalan/Spanish instead of staying in English regardless of the UI language.

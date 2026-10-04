# Fixes

## Messages and field labels shown in English to Catalan and Spanish users:

- 14 messages raised from Python had no Catalan/Spanish translation and always showed in
  English: guard mode access, the automatic check-in failure notice, overlapping sessions,
  deleting an enrollment that already has grades, converting a group with students to
  reinforcement, the classroom-change wizard, groups with no classroom in the schedule import,
  duplicate pre-enrolments, the missing "current course" setting, and others. Three more ("Send
  reminder", "Open surveys", "Name") had a translation that Odoo never loaded for them, for lack
  of the code reference and its `#. odoo-python` marker.
- 6 texts from the web client (JavaScript) had no translation: archiving groups, "Processing,
  please wait...", the guard board's "Patio", among others; 5 more were translated but never
  loaded for the same reason.
- 89 labels of fields EMS defines had no Catalan/Spanish translation (including the attendance
  correction list's "Employee", "Attendance" and "Status" columns, and many strike, group,
  classroom and wizard fields).

# Internal changes

## Automatic check for untranslated texts:

- New `tests/test_i18n_coverage.py`: fails when a `_()` string in EMS's Python code or a `_t()`
  in the web client has no Catalan/Spanish entry (or lacks the marker Odoo needs to load it),
  and when a field EMS defines has no Catalan/Spanish label. A new feature can no longer ship
  untranslated texts of these kinds without CI going red. It also checks that one of the fixed
  messages really loads in both languages at runtime.
- The earlier estimate in the issue (149 untranslated Python strings) counted JavaScript blocks
  by mistake: those carry a different marker and were fine.

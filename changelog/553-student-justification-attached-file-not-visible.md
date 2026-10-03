# Fixes

## Attendance justification and study attachments visible to everyone who can see the record:
- The files a tutor attached to an attendance justification were stored without being tied to
  the justification (no `res_id`), and Odoo only lets the uploader (or a system admin) read such
  an attachment: Head of Studies, Deputy Head of Studies and the teachers of the affected
  sessions saw an empty "Attached files" tab (issue #553).
- `ems.attendance_justification`'s `create()`/`write()` now tie every uploaded file to its
  justification, through a new shared `ir.attachment._ems_link_to()` (also reused by
  `ems.convalidation`, which had its own copy of the same logic), so files follow the
  justification's own access rules.
- The same bug hid the official curricula (BOE/DOGC documents loaded from
  `data/cat/attachments/`) attached to each study from every teacher and the secretary's office:
  `ems.study`'s `create()`/`write()` now link them too, so the study CSV's own reload on upgrade
  ties the shipped curricula to their study (a curriculum shared by several studies goes to the
  first one).
- `migrations/18.0.0.33.0/post-migrate.py` links the attachments already stored for both models
  (10 justification files and 115 study files in the dev DB), files uploaded by hand included.
- Tests: `TransactionCase` regressions for both models (another role reads the file, files added
  on create/write are linked, the shipped curricula are linked after data load), plus a Head of
  Studies tour on a justification and a teacher tour on a study, both opening the "Attached
  files" tab.

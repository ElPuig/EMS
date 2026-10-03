# Fixes

## Attendance justification attachments visible to everyone who can see the justification:
- The files a tutor attached to an attendance justification were stored without being tied to
  the justification (no `res_id`), and Odoo only lets the uploader (or a system admin) read such
  an attachment: Head of Studies, Deputy Head of Studies and the teachers of the affected
  sessions saw an empty "Attached files" tab (issue #553).
- `ems.attendance_justification`'s `create()`/`write()` now tie every uploaded file to its
  justification, through a new shared `ir.attachment._ems_link_to()` (also reused by
  `ems.convalidation`, which had its own copy of the same logic), so files follow the
  justification's own access rules.
- `migrations/18.0.0.32.1/post-migrate.py` links the attachments already stored (10 in the dev
  DB).
- Tests: two `TransactionCase` regressions (Head of Studies reads a tutor's file; a file added
  later is linked) and a Head of Studies tour opening the "Attached files" tab.

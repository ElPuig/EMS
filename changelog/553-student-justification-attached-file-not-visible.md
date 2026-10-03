# What's new

## Simpler "Attached files" tab (justifications and studies):
- Files are uploaded straight from the tab (one button, several files at once, each named after
  its file): no more "Add a line" dialog, nor a list of existing files to pick from.
- Every file shows three matching icons: preview in Odoo's own file viewer (the chatter's: PDFs,
  images, text, video), download and delete. Deleting really deletes the file on save, unless
  another record still uses it (an official curriculum shared by several studies).
- New shared `ems.attachment_mixin` (server: ties each file to its record, deletes removed ones)
  and `ems_attachments` field widget (client, extends the stock `many2many_binary`), documented in
  `docs/en/developers/shared/attachments.md`. The old list's `ir.attachment.download()` button
  method is gone. Tutor and admin manuals updated in the three languages, with the tutors'
  "Attached files" screenshot regenerated.

# Fixes

## Attendance justification and study attachments visible to everyone who can see the record:
- The files a tutor attached to an attendance justification were stored without being tied to
  the justification (no `res_id`), and Odoo only lets the uploader (or a system admin) read such
  an attachment: Head of Studies, Deputy Head of Studies and the teachers of the affected
  sessions saw an empty "Attached files" tab (issue #553).
- Both models now tie every uploaded file to its record (`ems.attachment_mixin`, built on a new
  shared `ir.attachment._ems_link_to()` that `ems.convalidation`, which had its own copy of the
  same logic, reuses too), so files follow the record's own access rules.
- The same bug hid the official curricula (BOE/DOGC documents loaded from
  `data/cat/attachments/`) attached to each study from every teacher and the secretary's office;
  the study CSV's own reload on upgrade
  ties the shipped curricula to their study (a curriculum shared by several studies goes to the
  first one).
- `migrations/18.0.0.33.0/post-migrate.py` links the attachments already stored for both models
  (10 justification files and 115 study files in the dev DB), files uploaded by hand included.
- Tests: `TransactionCase` regressions for both models (another role reads the file, files added
  on create/write are linked, the shipped curricula are linked after data load), plus a Head of
  Studies tour on a justification and a teacher tour on a study, both opening the "Attached
  files" tab and previewing the file, and a tutor tour uploading a file and deleting another.
- The study CRUD tour's deletion check only passed by accident (its bare `.o_list_view` matched the
  next study's embedded attachments list, since Odoo opens the next record after a delete): it now
  goes back to the list explicitly.

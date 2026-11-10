# Fixes

## Meeting minutes take their annexes as files uploaded from the computer:
- The minute's Annexes block only let the writer link controlled documents already registered in Quality (`ems.quality.document`, `annex_document_ids`), so a PDF from one's own computer could not be attached. That link list is gone (field removed): the block is now an *Attached files* upload (`annex_attachment_ids`, native `many2many_binary`), and the minute's PDF lists the files.
- A file uploaded while the minute is still unsaved belongs to no record, so only its uploader could open it: on save it is linked to the minute (`_ems_link_annex_files`), so whoever reads the minute can download it. Only the files the person saving uploaded are taken over.
- The annexes become read-only once the minute is approved, like the rest of its content.
- The upgrade drops the old link table (`ems_minute_annex_rel`, empty in production when checked on 2026-11-10): Odoo leaves the table of a removed field behind.

# Fixes

## Meeting minutes accept files uploaded from the computer as annexes:
- The minute's Annexes block only let the writer link controlled documents already registered in Quality (`ems.quality.document`), so a PDF from one's own computer could not be attached. A new *Attached files* upload (`annex_attachment_ids`, native `many2many_binary`) sits next to that list, and the minute's PDF lists both kinds of annex.
- A file uploaded while the minute is still unsaved belongs to no record, so only its uploader could open it: on save it is linked to the minute (`_ems_link_annex_files`), so whoever reads the minute can download it. Only the files the person saving uploaded are taken over.
- Both annex lists become read-only once the minute is approved, like the rest of its content.

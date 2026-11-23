# Technical Reference: a record's own files (`ems.attachment_mixin` + `ems_attachments`)

## Overview

Some models keep their own files in an `attachment_ids` many2many to `ir.attachment`, edited from
an "Attached files" tab: `ems.attendance_justification` (the justificant a tutor uploads) and
`ems.study` (its official curricula). Two shared pieces make that tab work the same everywhere:

| Piece | File | Role |
|-------|------|------|
| `ems.attachment_mixin` | `models/shared/attachment.py` | Server side: ties every file to its record, deletes a removed one |
| `ems_attachments` field widget | `static/src/js/backend/attachments_field.js` + `static/src/xml/backend/attachments_field.xml` | Client side: direct upload, and preview / download / delete on every file |

Usage, model side: `_inherit = [..., 'ems.attachment_mixin']` plus the model's own `attachment_ids`
field. View side: `<field name="attachment_ids" widget="ems_attachments" nolabel="1"/>`.

```mermaid
flowchart TD
    U([User]) -->|"Attached files button"| W[ems_attachments widget]
    W -->|"FileInput: /web/binary/upload_attachment"| A[(ir.attachment\nname = file name)]
    W -->|"save: attachment_ids commands"| M["ems.attachment_mixin\ncreate() / write()"]
    M -->|"_ems_link_to(): res_model/res_id, sudo"| A
    M -->|"removed from attachment_ids\nand held by no other record"| D[["unlink()"]]
    W -->|"eye"| V["Odoo FileViewer\n(PDF, images, text, video)"]
    W -->|"download"| C["/web/content/id?download=true"]
```

---

## Who can read a file

Odoo only lets the uploader (or a system admin) read an attachment with no `res_id`
(`ir.attachment.check()`/`_search()`). The mixin's `create()` and `write()` (when `attachment_ids`
is in `vals`) call `ir.attachment._ems_link_to(record)`, which sets `res_model`/`res_id` on the
files still unlinked, with `sudo()`. From then on a file follows its record's own read access:
whoever can read the justification (the tutor and the chiefs above them, the teachers of the
affected sessions, Head of Studies through `group_student_data_reader`, the academic
administration) or the study (every teacher, the secretary's office, the academic administration)
can open it. Issue #553: Head of Studies saw an empty tab on justifications, and teachers on
studies. `migrations/18.0.0.33.0/post-migrate.py` links the files stored before the fix.

`ir.attachment._ems_link_to()` is also used on its own by `ems.convalidation`, whose files come
from the portal and are never deleted from the form.

---

## Deleting a file

The widget offers no list of existing files to pick from, so a file removed from the record could
never be attached again: the mixin's `write()` deletes it. Only the files tied to that record
(`res_model`/`res_id`) are candidates, and one still held by another record of the same model is
kept - an official curriculum shared by several studies stays tied to the first one
(`_ems_link_to()` never re-links a file), which gives the same access since no record rule
restricts `ems.study`. That check searches with `sudo()` and `active_test=False`, so a holder the
user cannot read, or an archived one, still counts. The deletion itself runs with the user's own
rights: Odoo allows it to whoever can write the record.

The study data files keep their curricula linked on their own: `data/cat/ems.study.csv` reloads
on every upgrade (`noupdate=False`) and that `write()` links any file still unlinked. A file an
admin adds by hand to a study shipped in `data/` is dropped by that same reload (the CSV owns the
list), and the mixin then deletes it.

---

## The widget

`EmsAttachmentsField` extends Odoo's `Many2ManyBinaryField` (`many2many_binary`): the same
`FileInput` upload (several files at once, each named after its file), the same `onFileRemove()`.
Its template replaces the stock file card with one row per file - the mimetype icon, the name and
three matching icon buttons:

| Button | Shown | Action |
|--------|-------|--------|
| Preview (`fa-eye`) | `FileModel.isViewable` (PDF, images, text, video) | Odoo's own `FileViewer` (`@web/core/file_viewer`, the chatter's), browsing every viewable file of the field |
| Download (`fa-download`) | always | `/web/content/<id>?download=true` |
| Delete (`fa-trash`) | the field is editable | removes the file from the record; the mixin deletes it on save |

`files` builds `FileModel` objects from each record's `name`/`mimetype`/`checksum` (`checksum` is
added to the stock widget's `relatedFields`). The upload button and the delete icon follow the
field's `readonly`: a user who cannot write the model gets a read-only form from Odoo itself
(`ir.ui.view` sets `edit="False"`), and the justification form also makes the field read-only for
anyone but the student's tutor or an admin.

---

## Compression of uploaded files (issue #799)

Every PDF and JPEG/PNG stored as an `ir.attachment` (widget uploads, `Binary(attachment=True)`
fields, portal and wizards alike) is shrunk in the background. `models/shared/attachment.py`
overrides `create()` and `write()` (when `raw`/`datas` change): the file is stored exactly as
uploaded, and a `queue_job` job (`_ems_compress`, one waiting job per file) replaces it later, so a
scan that takes seconds to process never delays the user's request.

```mermaid
flowchart LR
    U([Upload]) --> C["ir.attachment create()/write()"]
    C -->|"stored as uploaded"| F[(filestore)]
    C -->|"candidate? PDF/JPEG/PNG, over ems.compress_min_kb, not excluded"| J[["queue_job: _ems_compress"]]
    J --> E["ems.file_compression.compress()"]
    E -->|"saves at least 10 %"| W["write(raw), ems_no_compress"]
    E -->|"otherwise"| K["original kept"]
```

| Piece | Rule |
|-------|------|
| Candidates | `type='binary'`, PDF/JPEG/PNG, larger than `ems.compress_min_kb` (default 300 KB). PDFs only when `gs` is installed |
| Never compressed | files loaded from `data/` (`install_mode`: the official curricula, which every upgrade loads again from the CSV, so a compressed copy would be undone and queued again each time), `ir.ui.view`, `ir.actions.report`, `mail.mail`, `mail.compose.message` and `ems.signed.record` attachments, `ems.erasmus.call.template_file`, and `image.mixin`'s image fields (`image_1920`... `image_128`) |
| PDF engine | Ghostscript (`apt-requirements.txt`), `/ebook` profile (150 dpi), 120 s timeout, files on disk (never the whole PDF twice in memory). Not touched: a PDF with a digital signature (`/ByteRange`, the signature covers the exact bytes) or encrypted |
| Image engine | Odoo's `ImageProcess`: upright, long side at most 1920 px, JPEG quality 85, no EXIF (a phone photo carries the GPS position). A PNG without transparency is stored as JPEG (the name becomes `.jpg`); one with transparency stays PNG |
| Acceptance | The result replaces the file only if it is at most 90 % of the original and a PDF keeps its number of pages. The original is not kept |
| Failure | A broken PDF, a timeout or a missing `gs` is logged as a WARNING and the file stays as uploaded |

**Why not Odoo's own image handling alone:** `ir.attachment._postprocess_contents()` already
resizes an image above `base.image_autoresize_max_px` (1920x1920) when it is stored, but it neither
re-encodes an image that already fits, nor converts a large PNG to JPEG, nor drops the EXIF
metadata, and it never touches a PDF. `ems.file_compression` covers exactly that remainder, with
the same 1920 px limit.

**Cost** (synthetic scans, this box, `odoo shell`): a lossless A4 scan of 9.7 MB becomes 1.1 MB
(about 88 % less) in 0.2 s for one page and 1.9 s for fifteen (roughly 0.13 s per page); a 1900x1200
PNG of 6.9 MB becomes 1.5 MB in 0.07 s; peak memory of the process stays under 400 MB. The
filestore of this development database holds no file contents, so a sample of real documents could
not be measured. The job processes one file at a time on the queue: the cost grows linearly with
the pages uploaded.

**Files stored before the feature.** `migrations/18.0.0.51.0/post-migrate.py` calls
`ir.attachment._ems_queue_existing_compression()`, which only *queues* the jobs (a `search()` on the
same domain as a new upload, minus the files with an external id, at priority 20 so emails and
notices go first): the upgrade takes about a second whatever the number of files, and the jobs run
afterwards, one at a time, on the queue. A clean install has no files, so there is no
`post_init_hook` equivalent. Running it twice queues nothing new (`identity_key`).

**Photos of families' data requests.** `contact_data_request._ems_photo_from_upload()` keeps its own
checks (JPEG/PNG only, 10 MB limit, user-facing messages) and uses `ems.file_compression.to_jpeg()`
for the processing, the same step as any other image (upright, 1920 px, JPEG quality 85, no EXIF).

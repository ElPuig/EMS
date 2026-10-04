# Orphan ESO curriculum attachment (Tecnologia i Digitalització)

**Status:** current as of 2026-10-03 (found while fixing issue #553). Not started: the developer
chose to leave it as is for now.

## The gap

`data/cat/attachments/eso/ir.attachment.csv` ships `ems.cur_tecno_digi_eso_2024_v1`
("Currículum: Tecnologia i Digitalització"), but no `ems.study` row in `data/` lists it in its
`attachment_ids:id` column. It is loaded into every installation yet attached to no study, so it
never shows in any study's "Attached files" tab, and since #553 links curricula to their study
through `ems.study.create()`/`write()`, it is also the one study attachment left without a
`res_id` (only a system admin can read it).

## Open questions

- Which ESO study (or studies) should list it in `data/cat/ems.study.csv`?
- Or is it obsolete and should it be removed from the attachments CSV instead?

Once decided, the study CSV's reload on upgrade links it on its own: no migration needed.

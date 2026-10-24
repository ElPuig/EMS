# What's new

## Erasmus+ document records (project, mobility, participant) and verifiable ZIP exports:

- Replaces the project dossier in SEPIE's 13 folders (phase 6, never released): a project's documents are now organised in five categories (01 Project, 02 Mobilities, 03 Finances, 04 Impact and dissemination, 05 Final report and audit) and each participant's record in four (01 Data and authorisations, 02 Before, 03 During, 04 After the mobility). Decided by the Erasmus coordinator.
- The call's documents stay the only list of what is required: each call document now has a category in the record (new calls preset it), and each document of a participant shows a status (missing, pending review, needs changes, complete, optional, not applicable). A document to sign is only complete once the team marks it valid, never just because a file was uploaded.
- Mobility form: the "Documents" tab becomes "Record", ordered by category, with the documents still missing, the application's documents (ID, CV...) and "Other documents" (project documents about the participant, e.g. an incident, or shared with others without copying the file). Project form: a "Documentation" tab with the five categories and how many records are complete, the mobilities with their record progress and a button to open each one, and an "Exports" tab.
- Portal: "My record" shows the documents grouped by the four categories, with their status, how many are still missing, and download links for the files already uploaded; uploading again adds a new version and keeps the earlier ones.
- "Export the record" (mobility) and "Export the project" (project) download a ZIP with the original files (signed PDFs untouched, every version numbered), an index of every document including the missing ones (index.csv), a manifest (manifest.json) and the SHA-256 hash of each file (SHA256SUMS) to verify the copy archived in Drive. In a project export a document shared by several participants is written once and referenced from their records. Built on the fly and streamed, never stored or held in memory.
- Each export is logged (who, when, what, files, documents missing, the ZIP's hash) and downloaded once by whoever asked for it. Confidential documents (health card, inclusion, bank data, confidential project documents) only leave EMS in an "audit export", which only the Erasmus coordinator or the administrator can ask for, with a reason.
- History kept: a file can no longer be removed from a valid document or a closed mobility (a new version is uploaded instead), every review change is written in the mobility's chatter with who made it, and uploads refuse programs, scripts and web pages and keep only the file's own name.
- Keeping period: counted from the date SEPIE paid the grant's balance (3 years, 5 above 60,000 €), empty until it is known, plus a "keep while an audit or request is pending" flag; nothing is ever deleted automatically.

# Internal changes

## Erasmus+ records code and tests:

- New `models/erasmus/records.py` (categories, safe names, upload checks) and `models/erasmus/export.py` (`ems.erasmus.export`, the log and ZIP builder, route `/ems/erasmus/export/<id>` replacing `/ems/erasmus/project/<id>/dossier`); `sepie_folder` replaced by `file_category`, the project document's `folder` by `category`. No migration: none of the Erasmus+ models is in production yet.
- New `tests/test_erasmus_records.py` (classification, status, history, uploads, permissions, record and project exports, hashes, confidential and audit exports, path safety, download once); the dossier tests of `test_erasmus_grant.py` move there. Developer doc: `docs/en/developers/erasmus/records.md`.

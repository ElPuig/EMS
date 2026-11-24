# What's new

## Tutorship transfer (a student followed by another group's tutor):

- A student enrolled in 2nd year with 1st-year subjects pending who drops every 2nd-year subject stays in their 2nd-year group in Esfer@, but can now be followed by the 1st-year tutor. The secretary's office, academic administration and the Heads of Studies set "Tutorship transferred to" on the student's Studies tab, only to a group of the student's own study (e.g. SMX2A to SMX1C, never to DAW2A) (issue #807).
- New `res.partner.transferred_group_id`, plus `tutorship_group_id` (stored: the transferred group, or else the main group). `tutor_id` is now the stored `tutorship_group_id.tutor_id`, so every tutor record rule, tutor check and tutor notice (attendance issues, strikes, expected withdrawals, ex officio withdrawal case file, Erasmus+ notices and appeals, portal profile) moves to the new tutor with no rule changed. `official_tutor_id` shows the main group's tutor while a transfer is set.
- The official (Esfer@) tutor keeps what goes by group: grade sessions and the year record. Main group, enrollment, schedule declaration, shift and break period are unchanged.
- "My students", the students gathered by a student walkout proposal (and the school hours its emails wait for) and the LimeSurvey tutorship survey follow the tutorship group.
- The transfer ends on its own with the course transition, a withdrawal, or when the main group changes to the transferred group or to another study's. No migration: the stored fields are computed on upgrade and on a clean install.
- `res.partner.write()` now drops `tutor_id` (stored, it would otherwise overwrite the value instead of being ignored).
- Tests: `TestStudentTutorshipTransfer`, a transferred student in `TestExOfficioWithdrawal` (the case file is the follow-up tutor's) and `TestStudentWalkout` (they join their tutorship group's walkouts), and the `TestStudentTutorshipTransferTour` tours (the secretary transfers; the new tutor, as a plain teacher, finds the student in kanban/list/form and edits them). Manuals for the secretary, Heads of Studies and tutors (ca/es/en).

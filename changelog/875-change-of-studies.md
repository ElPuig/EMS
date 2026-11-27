# What's new

## Change of studies of a confirmed enrollment (issue #875):

- New "Change studies" action on a confirmed enrollment (secretary and academic administration): picks the new studies, the enrollment template of the same course and the destination group of the same shift. The enrollment is renamed after the new studies (same number) and takes the new template's subjects (the previous ones stay at quantity 0, Odoo's way of removing a line from a confirmed order, and are hidden on the enrollment form and on the family's portal) and the student is placed in the destination group with the new subjects, through the same placement used when confirming an enrollment, without freezing the year record (a change of studies happens during the course). Subjects of the previous studies that already have grades are kept and listed in a chatter note.
- Optional adjustment amount, 0 by default: a positive amount issues an invoice for it, a negative one a credit note (generic product "Ajust per canvi d'estudis").
- A student with a confirmed enrollment in force can no longer be given another study (directly or through a main group) on their form: EMS points to the enrollment's action instead. Students whose enrollment isn't managed in EMS are not affected.

# Changes

## Enrollment form: every action in the Actions dropdown (issue #875):

- The enrollment form's header actions, native ones included (Send by email, Confirm, Create invoice, Cancel, Set to quotation, payment capture), now live in the Actions dropdown together with "Change studies" and "Re-apply Benefits".

# Fixes

## Enrollments left on the old study after a manual change of studies (issue #875):

- Students moved to another study by hand kept their confirmed enrollment on the old one, so the portal kept reading it (a student studying DAM was offered DAW's modules when requesting convalidations). A migration realigns every confirmed enrollment of the running course whose study differs from the student's main group: header and code from the group, lines from the subjects the student is enrolled in, no invoice and no change to the student. 4 enrollments in the dev database (restored from production), 0.5 s.
- Confirming or placing an enrollment no longer enrols the student in a subject whose line is at quantity 0.

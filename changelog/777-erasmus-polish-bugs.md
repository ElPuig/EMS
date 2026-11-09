# Internal changes

## Why the Erasmus+ economy does not use Odoo's accounting:

- The Erasmus+ economy developer doc (docs/en/developers/erasmus/economy.md) now explains why grants, payments, invoices and expenses use their own models instead of `account.move`/`account.payment` (asked by Fer in the review of v18.0.0.46.0): most of it is the SEPIE grant, not accounting; a participant's grant is not a vendor bill; collective invoices are split among participants; and vendor-bill rights would let the Erasmus team edit every invoice of the centre. One question is left open for the Secretary: whether the centre's official accounting is kept outside EMS. The surveys are not documented as an exception: they move to EMS's LimeSurvey integration (issue #771).

# Fixes

## Erasmus+ polish: bugs found in the review of 46.0:

- The Erasmus team can see and edit a host entity's address, country, website, email, phone and OID, and those of its tutors: the contact form hid that block from them. It stays hidden for students' records. A team member must also be a teacher, because that form reads student data (both are today; documented).
- Years no longer show a thousands separator ("2.027") in the economic panel, the project form and the organisational support rates (the integer widget's option is `enable_formatting` in Odoo 18, not `format`).
- "Target" is now translated "Objectiu"/"Objetivo" (quality indicators, objectives of the minutes). The LimeSurvey survey's field is now "Audience" in English and keeps "Destinataris"/"Destinatarios".
- An invoice can no longer be for a group mobility and for participants at once (it was counted twice), and a group's invoice no longer shows as "Not assigned" in red. The constraint checks what is written from now on.
- The interest indicator's 0 / 0 (12.5) did not reproduce on the dev database and was dropped from the issue.

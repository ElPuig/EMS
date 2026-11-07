# Internal changes

## Why the Erasmus+ economy does not use Odoo's accounting:

- The Erasmus+ economy developer doc (docs/en/developers/erasmus/economy.md) now explains why grants, payments, invoices and expenses use their own models instead of `account.move`/`account.payment` (asked by Fer in the review of v18.0.0.46.0): most of it is the SEPIE grant, not accounting; a participant's grant is not a vendor bill; collective invoices are split among participants; and vendor-bill rights would let the Erasmus team edit every invoice of the centre. One question is left open for the Secretary: whether the centre's official accounting is kept outside EMS. The surveys are not documented as an exception: they move to EMS's LimeSurvey integration (issue #771).

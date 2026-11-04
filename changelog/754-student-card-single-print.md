# Fixes

## Student card printed alone lands on its back (and its file carries the student's name):

- A lone card in the last row of a sheet (one card, or any odd number) was centred on the front sheet while its back sat in the right column, so once printed double-sided the back did not land behind its front. The front now keeps the left column (an empty cell on its right), mirroring the back.
- Downloading a single card names the file `Carnet d'estudiant - <student> - <course>` (translated) instead of the generic `Carnets d'estudiant - <course>`. A download of several cards keeps the report's name, as Odoo only applies the per-record name to a single record.

# Fixes

## Certificates (former students found in the Student field):

- The Student dropdown of a certificate request now offers archived contacts: former students and withdrawals are archived when they graduate or leave, so the secretariat could not choose them and had to register them as if they were not in EMS. Expelled students are accepted too.
- Choosing a former student fills in their personal email, never the centre's corporate one: a legacy contact that still keeps the corporate address in its email gets an empty field, for the secretariat to write the personal one.

# Changes

## Certificates (details tab with hints and validated values):

- The request's Certificate details tab is now a three-column list (detail, hint, value) instead of one column per data type, most of them empty; a click on a line opens a dialog with only the input of its type (date picker, number, text, company search with Create company).
- Every detail type can carry a hint (what to write and how, with an example), shown to the applicant on the portal and to the staff in the request.
- Values are validated, with one check shared by the backend and the portal: a school year must be written as 2024-25 or 2024-2025 with consecutive years (stored as 2024-25), and a date can be configured not to be earlier than another one (Not before). The portal reports a wrong detail instead of silently dropping it, and a step cannot be done while a value written before this check is still wrong.
- The FCT certificate's school year is now called "Curs acadèmic", every FCT detail has a hint, and its end date cannot be earlier than its start date (a migration applies it to existing installations, only where the centre has not changed those details).
